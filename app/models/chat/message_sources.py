from uuid import UUID, uuid4

from sqlalchemy import Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.constants.constants_database import SCHEMA_NAME
from app.models.common.mixins import TimestampMixin


class MessageSource(TimestampMixin, Base):
    """Citation link between an assistant message and the document/chunk it used."""

    __tablename__ = "message_sources"
    __table_args__ = {"schema": SCHEMA_NAME}

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    message_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey(f"{SCHEMA_NAME}.chat_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey(f"{SCHEMA_NAME}.documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        # Keep the source row even if an individual chunk is removed later.
        ForeignKey(f"{SCHEMA_NAME}.document_chunks.id", ondelete="SET NULL"),
    )
    # Higher score usually means the retrieved chunk matched the question better.
    similarity_score: Mapped[float | None] = mapped_column(Float)

    message: Mapped["ChatMessage"] = relationship(back_populates="sources")
    document: Mapped["Document"] = relationship(back_populates="message_sources")
    chunk: Mapped["DocumentChunk | None"] = relationship(back_populates="message_sources")
