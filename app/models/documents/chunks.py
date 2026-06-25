from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.constants.database import SCHEMA_NAME
from app.models.common.mixins import TimestampMixin


class DocumentChunk(TimestampMixin, Base):
    """Smaller text slice of a document for future vector search/RAG retrieval."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        # Each document can have chunk 0, chunk 1, etc., but not duplicates.
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="document_chunks_unique_index",
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
        # If a document is deleted, its chunks should be deleted too.
        ForeignKey(f"{SCHEMA_NAME}.documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # token_count helps control prompt size when sending chunks to an AI model.
    token_count: Mapped[int | None] = mapped_column(Integer)
    # embedding_id can point to a vector database record later.
    embedding_id: Mapped[str | None] = mapped_column(Text)

    document: Mapped["Document"] = relationship(back_populates="chunks")
    message_sources: Mapped[list["MessageSource"]] = relationship(back_populates="chunk")
