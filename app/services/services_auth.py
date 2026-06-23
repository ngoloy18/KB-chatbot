from datetime import UTC, datetime
from secrets import token_urlsafe
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.constants_auth import JWT_SUBJECT_CLAIM, USER_ROLE_USER
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.repositories.repositories_users import user_repository
from app.schemas.schemas_auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.exceptions_auth import (
    DuplicateEmailError,
    EmailNotVerifiedError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidVerificationTokenError,
)


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
        return RegisterResponse(
            user=UserResponse.model_validate(user),
            verification_token=verification_token,
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

        # Load the user again so disabled/deleted accounts cannot keep refreshing.
        user = await user_repository.get_by_id(db, user_id)
        if user is None:
            raise InvalidCredentialsError("Invalid or expired refresh token.")
        if not user.is_active:
            raise InactiveUserError("This user is inactive.")

        access_token = create_access_token(user_id=user.id, role=user.role)
        return TokenResponse(access_token=access_token)


auth_service = AuthService()
