from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.constants.constants_database import SCHEMA_NAME
from app.models.mixins import TimestampMixin


class User(TimestampMixin, Base):
    """Application user account used for ownership and future authentication."""

    __tablename__ = "users"
    __table_args__ = (
        # Limit role values at the database level so invalid roles cannot be saved.
        CheckConstraint("role IN ('admin', 'user')", name="users_role_check"),
        {"schema": SCHEMA_NAME},
    )

    # UUID primary keys are safer for public APIs than auto-increment integers.
    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    # Email is unique because it will be the login identifier later.
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # Store only a password hash, never a plain-text password.
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Email verification proves the user controls the email used for login.
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    # The token is temporary proof used by /auth/verify-email.
    email_verification_token: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
    )
    email_verification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    # Relationships let SQLAlchemy navigate from one user to related records.
    documents: Mapped[list["Document"]] = relationship(back_populates="creator")
    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user")
    document_permissions: Mapped[list["DocumentPermission"]] = relationship(
        back_populates="user"
    )
