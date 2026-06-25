from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.constants.auth import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    PASSWORD_REQUIREMENTS_DESCRIPTION,
    TOKEN_TYPE_BEARER,
)


def validate_strong_password(password: str) -> str:
    """Validate password complexity shared by registration and reset."""

    checks = [
        (any(character.isupper() for character in password), "uppercase letter"),
        (any(character.islower() for character in password), "lowercase letter"),
        (any(character.isdigit() for character in password), "number"),
        (
            any(not character.isalnum() for character in password),
            "special character",
        ),
    ]
    missing_requirements = [
        requirement
        for passed, requirement in checks
        if not passed
    ]
    if missing_requirements:
        raise ValueError(
            "Password must include at least one "
            + ", one ".join(missing_requirements)
            + "."
        )
    return password


class RegisterRequest(BaseModel):
    """Request body for normal user registration."""

    # EmailStr validates email format before the service runs.
    email: EmailStr
    # Password limits prevent empty passwords and unreasonably large request bodies.
    password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description=PASSWORD_REQUIREMENTS_DESCRIPTION,
        examples=["Password123!"],
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User's full name is required during registration.",
        examples=["Loy Ngo"],
    )

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, password: str) -> str:
        """Reject weak passwords before the service creates a user."""

        return validate_strong_password(password)


class LoginRequest(BaseModel):
    """Request body for logging in with email and password."""

    email: EmailStr
    password: str = Field(
        ...,
        min_length=1,
        max_length=PASSWORD_MAX_LENGTH,
        description="Use the password created during registration.",
        examples=["Password123!"],
    )


class TokenResponse(BaseModel):
    """JWT tokens returned after successful login or refresh."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = TOKEN_TYPE_BEARER


class RefreshTokenRequest(BaseModel):
    """Request body for getting a new access token."""

    refresh_token: str = Field(
        ...,
        min_length=16,
        description="Refresh token returned by the login endpoint.",
    )


class LogoutResponse(BaseModel):
    """Response returned after a refresh token is revoked."""

    message: str


class ForgotPasswordRequest(BaseModel):
    """Request body for starting a password reset."""

    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    """Password reset response with local-development reset token."""

    message: str
    email_sent: bool = False
    # Returned only when EMAIL_RETURN_DEV_TOKENS=true for local Swagger testing.
    reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    """Request body for replacing a password with a reset token."""

    token: str = Field(..., min_length=16, max_length=255)
    new_password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description=PASSWORD_REQUIREMENTS_DESCRIPTION,
        examples=["NewPassword123!"],
    )

    @field_validator("new_password")
    @classmethod
    def new_password_must_be_strong(cls, password: str) -> str:
        """Reject weak replacement passwords before changing stored credentials."""

        return validate_strong_password(password)


class VerifyEmailRequest(BaseModel):
    """Request body for confirming a registered email address."""

    token: str = Field(..., min_length=16, max_length=255)


class ResendVerificationRequest(BaseModel):
    """Request body for sending a new verification email."""

    email: EmailStr


class ResendVerificationResponse(BaseModel):
    """Response for verification email resend requests."""

    message: str
    email_sent: bool = False
    # Returned only when EMAIL_RETURN_DEV_TOKENS=true for local Swagger testing.
    verification_token: str | None = None


class UserResponse(BaseModel):
    """Safe user shape returned by auth endpoints."""

    # Lets Pydantic build this response directly from a SQLAlchemy User object.
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str | None = None
    role: str
    is_active: bool
    is_email_verified: bool
    created_at: datetime


class RegisterResponse(BaseModel):
    """Registration response with local-development verification token."""

    user: UserResponse
    message: str = "User registered. Please verify your email before login."
    email_sent: bool = False
    # Returned only when EMAIL_RETURN_DEV_TOKENS=true for local Swagger testing.
    verification_token: str | None = None
