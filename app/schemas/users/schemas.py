from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.constants.auth import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    PASSWORD_REQUIREMENTS_DESCRIPTION,
    USER_ROLE_ADMIN,
    USER_ROLE_USER,
)
from app.schemas.auth.schemas import validate_strong_password


USER_ROLE_PATTERN = f"^({USER_ROLE_ADMIN}|{USER_ROLE_USER})$"


class UserUpdateRequest(BaseModel):
    """Admin request body for editing a user account."""

    # All fields are optional so admins can update only one user property.
    email: EmailStr | None = Field(
        default=None,
        description="Changing email marks the user unverified and creates a new verification token.",
    )
    full_name: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None, pattern=USER_ROLE_PATTERN)
    is_active: bool | None = None
    is_email_verified: bool | None = None
    password: str | None = Field(
        default=None,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description=PASSWORD_REQUIREMENTS_DESCRIPTION,
    )

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, password: str | None) -> str | None:
        """Reject weak admin-set passwords before the service updates a user."""

        if password is None:
            return None
        return validate_strong_password(password)


class UserAdminResponse(BaseModel):
    """User shape returned to admins."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str | None = None
    role: str
    is_active: bool
    is_email_verified: bool
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    """Paginated admin response for users."""

    items: list[UserAdminResponse]
    total: int
    page: int
    page_size: int
