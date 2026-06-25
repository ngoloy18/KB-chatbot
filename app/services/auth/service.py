from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.constants_auth import (
    JWT_EXPIRES_AT_CLAIM,
    JWT_ID_CLAIM,
    JWT_SUBJECT_CLAIM,
    USER_ROLE_USER,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_token,
    hash_password,
    verify_password,
)
from app.core.config import settings
from app.repositories.auth.refresh_tokens import refresh_token_repository
from app.repositories.users.users import user_repository
from app.schemas.auth.schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LogoutResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.auth.exceptions import (
    DuplicateEmailError,
    EmailNotVerifiedError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidPasswordResetTokenError,
    InvalidVerificationTokenError,
)
from app.services.auth.email import email_service


class AuthService:
    """Business logic for registration, verification, and login."""

    async def register_user(
        self,
        db: AsyncSession,
        payload: RegisterRequest,
    ) -> RegisterResponse:
        """Create a normal unverified user account."""

        # Email must stay unique because login uses email as the account id.
        existing_user = await user_repository.get_by_email(db, payload.email)
        if existing_user is not None:
            raise DuplicateEmailError("A user with this email already exists.")

        verification_token = token_urlsafe(32)

        # Only the hashed password is saved; the plaintext password is never stored.
        user = await user_repository.create_user(
            db=db,
            email=payload.email,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
            role=USER_ROLE_USER,
            is_email_verified=False,
            email_verification_token=verification_token,
            email_verification_sent_at=datetime.now(UTC),
        )
        await email_service.send_verification_email(user.email, verification_token)
        return RegisterResponse(
            user=UserResponse.model_validate(user),
            verification_token=(
                verification_token
                if settings.email_return_dev_tokens
                else None
            ),
        )

    async def verify_email(
        self,
        db: AsyncSession,
        payload: VerifyEmailRequest,
    ) -> UserResponse:
        """Mark a user email as verified when the token matches."""

        user = await user_repository.get_by_verification_token(db, payload.token)
        if user is None:
            raise InvalidVerificationTokenError("Invalid email verification token.")

        user.is_email_verified = True
        user.email_verification_token = None
        await db.commit()
        await db.refresh(user)
        return UserResponse.model_validate(user)

    async def login(self, db: AsyncSession, payload: LoginRequest) -> TokenResponse:
        """Verify credentials and return JWT access and refresh tokens."""

        user = await user_repository.get_by_email(db, payload.email)
        # Use the same error for missing users and wrong passwords so attackers
        # cannot easily guess which emails are registered.
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise InvalidCredentialsError("Incorrect email or password.")
        if not user.is_active:
            raise InactiveUserError("This user is inactive.")
        if not user.is_email_verified:
            raise EmailNotVerifiedError("Please verify your email before logging in.")

        # Access tokens are sent to protected endpoints in Authorization headers.
        # Refresh tokens are kept by the client and used only to request new access.
        access_token = create_access_token(user_id=user.id, role=user.role)
        refresh_token = create_refresh_token(user_id=user.id)
        await self._store_refresh_token(db, user.id, refresh_token)
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)

    async def refresh_token(
        self,
        db: AsyncSession,
        payload: RefreshTokenRequest,
    ) -> TokenResponse:
        """Use a valid refresh token to create a new access token."""

        try:
            token_payload = decode_refresh_token(payload.refresh_token)
            user_id = UUID(str(token_payload.get(JWT_SUBJECT_CLAIM)))
        except (TypeError, ValueError):
            raise InvalidCredentialsError("Invalid or expired refresh token.")

        stored_token = await refresh_token_repository.get_active_by_hash(
            db,
            hash_token(payload.refresh_token),
        )
        if stored_token is None or stored_token.user_id != user_id:
            raise InvalidCredentialsError("Invalid or expired refresh token.")
        if stored_token.token_id != token_payload.get(JWT_ID_CLAIM):
            raise InvalidCredentialsError("Invalid or expired refresh token.")

        # Load the user again so disabled/deleted accounts cannot keep refreshing.
        user = await user_repository.get_by_id(db, user_id)
        if user is None:
            raise InvalidCredentialsError("Invalid or expired refresh token.")
        if not user.is_active:
            raise InactiveUserError("This user is inactive.")

        access_token = create_access_token(user_id=user.id, role=user.role)
        refresh_token = create_refresh_token(user_id=user.id)

        # Rotation means each refresh token can be used once, then replaced.
        await refresh_token_repository.revoke_token(db, stored_token)
        await self._store_refresh_token(db, user.id, refresh_token)
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)

    async def logout(
        self,
        db: AsyncSession,
        payload: RefreshTokenRequest,
    ) -> LogoutResponse:
        """Revoke one refresh token so it cannot create new access tokens."""

        try:
            decode_refresh_token(payload.refresh_token)
        except ValueError:
            raise InvalidCredentialsError("Invalid or expired refresh token.")

        stored_token = await refresh_token_repository.get_active_by_hash(
            db,
            hash_token(payload.refresh_token),
        )
        if stored_token is None:
            raise InvalidCredentialsError("Invalid or expired refresh token.")

        await refresh_token_repository.revoke_token(db, stored_token)
        return LogoutResponse(message="Logged out successfully.")

    async def _store_refresh_token(
        self,
        db: AsyncSession,
        user_id: UUID,
        refresh_token: str,
    ) -> None:
        """Save refresh token metadata needed for refresh and logout."""

        token_payload = decode_refresh_token(refresh_token)
        expires_at = datetime.fromtimestamp(
            int(token_payload[JWT_EXPIRES_AT_CLAIM]),
            UTC,
        )
        await refresh_token_repository.create_token(
            db=db,
            user_id=user_id,
            token_hash=hash_token(refresh_token),
            token_id=str(token_payload[JWT_ID_CLAIM]),
            expires_at=expires_at,
        )

    async def forgot_password(
        self,
        db: AsyncSession,
        payload: ForgotPasswordRequest,
    ) -> ForgotPasswordResponse:
        """Create a password reset token for an existing active user."""

        user = await user_repository.get_by_email(db, payload.email)
        # Use the same public message for existing and missing emails so attackers
        # cannot use this endpoint to discover registered accounts.
        public_message = "If that email exists, a password reset token was created."
        if user is None or not user.is_active:
            return ForgotPasswordResponse(message=public_message)

        reset_token = token_urlsafe(32)
        user.password_reset_token_hash = hash_token(reset_token)
        user.password_reset_sent_at = datetime.now(UTC)
        await db.commit()
        await email_service.send_password_reset_email(user.email, reset_token)
        return ForgotPasswordResponse(
            message=public_message,
            reset_token=reset_token if settings.email_return_dev_tokens else None,
        )

    async def reset_password(
        self,
        db: AsyncSession,
        payload: ResetPasswordRequest,
    ) -> UserResponse:
        """Replace a user's password when a valid reset token is provided."""

        user = await user_repository.get_by_password_reset_token_hash(
            db,
            hash_token(payload.token),
        )
        if user is None or user.password_reset_sent_at is None:
            raise InvalidPasswordResetTokenError("Invalid or expired password reset token.")

        expires_at = user.password_reset_sent_at + timedelta(
            minutes=settings.password_reset_token_expire_minutes
        )
        if datetime.now(UTC) > expires_at:
            raise InvalidPasswordResetTokenError("Invalid or expired password reset token.")
        if not user.is_active:
            raise InactiveUserError("This user is inactive.")

        # Saving a new hash replaces the old password without storing plaintext.
        user.hashed_password = hash_password(payload.new_password)
        user.password_reset_token_hash = None
        user.password_reset_sent_at = None
        await db.commit()
        await db.refresh(user)
        return UserResponse.model_validate(user)


auth_service = AuthService()
