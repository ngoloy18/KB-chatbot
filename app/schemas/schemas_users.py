from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserUpdateRequest(BaseModel):
    """Admin request body for editing a user account."""

    # All fields are optional so admins can update only one user property.
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None, pattern="^(admin|user)$")
    is_active: bool | None = None
    is_email_verified: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


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
