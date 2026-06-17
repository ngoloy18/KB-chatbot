from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.constants import SCHEMA_NAME
from app.models.mixins import TimestampMixin


if TYPE_CHECKING:
    from app.models.models_chat_sessions import ChatSession


class AIRun(TimestampMixin, Base):
    """Metadata about one AI model call for debugging and usage tracking."""

    __tablename__ = "ai_runs"
    __table_args__ = (
        # A run is either recorded as successful or failed.
        CheckConstraint("status IN ('success', 'failed')", name="ai_runs_status_check"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    session_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey(f"{SCHEMA_NAME}.chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_message_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey(f"{SCHEMA_NAME}.chat_messages.id", ondelete="SET NULL"),
    )
    assistant_message_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey(f"{SCHEMA_NAME}.chat_messages.id", ondelete="SET NULL"),
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Token counts help estimate model cost and prompt size.
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    # Store provider/error details when status is failed.
    error_message: Mapped[str | None] = mapped_column(Text)

    session: Mapped["ChatSession"] = relationship(back_populates="ai_runs")
