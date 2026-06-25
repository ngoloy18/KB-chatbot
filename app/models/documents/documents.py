from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.documents import (
    DOCUMENT_STATUS_FAILED,
    DOCUMENT_STATUS_PROCESSING,
    DOCUMENT_STATUS_READY,
    DOCUMENT_STATUS_UPLOADED,
)
from app.core.config import DocumentCategory
from app.db.base import Base
from app.constants.database import SCHEMA_NAME
from app.models.common.mixins import TimestampMixin


class Document(TimestampMixin, Base):
    """Uploaded knowledge-base document stored for AI retrieval and CRUD APIs."""

    __tablename__ = "documents"
    __table_args__ = (
        # Status describes where the document is in the upload/processing pipeline.
        CheckConstraint(
            "status IN "
            f"('{DOCUMENT_STATUS_UPLOADED}', '{DOCUMENT_STATUS_PROCESSING}', "
            f"'{DOCUMENT_STATUS_READY}', '{DOCUMENT_STATUS_FAILED}')",
            name="documents_status_check",
        ),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    # API calls use "name", but the database column is named "title".
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    # Category is normalized through a foreign key instead of duplicated text.
    category_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey(f"{SCHEMA_NAME}.document_categories.id"),
        nullable=False,
    )
    # File metadata records the original upload and where it was saved locally.
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_path: Mapped[str | None] = mapped_column(Text)
    file_type: Mapped[str | None] = mapped_column(String(50))
    # Content is stored as text so the app can search/read it immediately.
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=DOCUMENT_STATUS_UPLOADED,
    )
    # Nullable until authentication is implemented and every request has a user.
    created_by: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey(f"{SCHEMA_NAME}.users.id"),
    )

    # Relationships connect this document to category, owner, chunks, and sources.
    category: Mapped["DocumentCategoryModel"] = relationship(back_populates="documents")
    creator: Mapped["User | None"] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
    permissions: Mapped[list["DocumentPermission"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
    message_sources: Mapped[list["MessageSource"]] = relationship(
        back_populates="document"
    )

    @property
    def name(self) -> str:
        """Compatibility property for the existing API response field."""

        return self.title

    @property
    def category_name(self) -> DocumentCategory:
        """Return the category as the existing Python enum type."""

        return DocumentCategory(self.category.name)
