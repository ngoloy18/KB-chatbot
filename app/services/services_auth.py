from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.repositories_users import user_repository
from app.schemas.schemas_auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.exceptions_auth import (
    DuplicateEmailError,
    InactiveUserError,
    InvalidCredentialsError,
)


class AuthService:
    """Business logic for registration and login."""

    async def register_user(
        self,
        db: AsyncSession,
        payload: RegisterRequest,
    ) -> UserResponse:
        """Create a normal user account."""

        # Email must stay unique because login uses email as the account id.
        existing_user = await user_repository.get_by_email(db, payload.email)
        if existing_user is not None:
            raise DuplicateEmailError("A user with this email already exists.")

        # Only the hashed password is saved; the plaintext password is never stored.
        user = await user_repository.create_user(
            db=db,
            email=payload.email,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
            role="user",
        )
        return UserResponse.model_validate(user)

    async def login(self, db: AsyncSession, payload: LoginRequest) -> TokenResponse:
        """Verify credentials and return a JWT access token."""

        user = await user_repository.get_by_email(db, payload.email)
        # Use the same error for missing users and wrong passwords so attackers
        # cannot easily guess which emails are registered.
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise InvalidCredentialsError("Incorrect email or password.")
        if not user.is_active:
            raise InactiveUserError("This user is inactive.")

        # The token is what Swagger/clients send later in Authorization headers.
        token = create_access_token(user_id=user.id, role=user.role)
        return TokenResponse(access_token=token)


auth_service = AuthService()
