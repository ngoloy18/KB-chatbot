from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request body for normal user registration."""

    # EmailStr validates email format before the service runs.
    email: EmailStr
    # Password limits prevent empty passwords and unreasonably large request bodies.
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password must be at least 8 characters.",
        examples=["password123"],
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User's full name is required during registration.",
        examples=["Loy Ngo"],
    )


class LoginRequest(BaseModel):
    """Request body for logging in with email and password."""

    email: EmailStr
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Use the password created during registration.",
        examples=["password123"],
    )


class TokenResponse(BaseModel):
    """JWT returned after a successful login."""

    access_token: str
    token_type: str = "bearer"


class VerifyEmailRequest(BaseModel):
    """Request body for confirming a registered email address."""

    token: str = Field(..., min_length=16, max_length=255)


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
    # In production this token should be emailed, not shown in the API response.
    verification_token: str
