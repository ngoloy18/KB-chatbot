from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.permissions import (
    DOCUMENT_PERMISSION_OWNER,
    DOCUMENT_PERMISSION_READ,
    DOCUMENT_PERMISSION_WRITE,
)
from app.db.base import Base
from app.constants.database import SCHEMA_NAME
from app.models.common.mixins import TimestampMixin


class DocumentPermission(TimestampMixin, Base):
    """Per-user access rule for a document."""

    __tablename__ = "document_permissions"
    __table_args__ = (
        # Keep permission values predictable for authorization checks.
        CheckConstraint(
            "permission IN "
            f"('{DOCUMENT_PERMISSION_READ}', '{DOCUMENT_PERMISSION_WRITE}', "
            f"'{DOCUMENT_PERMISSION_OWNER}')",
            name="document_permissions_permission_check",
        ),
        # One user should have only one permission row per document.
        UniqueConstraint(
            "document_id",
            "user_id",
            name="document_permissions_unique_user_document",
        ),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    document_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey(f"{SCHEMA_NAME}.documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey(f"{SCHEMA_NAME}.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    permission: Mapped[str] = mapped_column(String(20), nullable=False)

    document: Mapped["Document"] = relationship(back_populates="permissions")
    user: Mapped["User"] = relationship(back_populates="document_permissions")
