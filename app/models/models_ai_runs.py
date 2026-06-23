from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.constants_ai import AI_RUN_STATUS_FAILED, AI_RUN_STATUS_SUCCESS
from app.db.base import Base
from app.constants.constants_database import SCHEMA_NAME
from app.models.mixins import TimestampMixin


class AIRun(TimestampMixin, Base):
    """Metadata about one AI model call for debugging and usage tracking."""

    __tablename__ = "ai_runs"
    __table_args__ = (
        # A run is either recorded as successful or failed.
        CheckConstraint(
            f"status IN ('{AI_RUN_STATUS_SUCCESS}', '{AI_RUN_STATUS_FAILED}')",
            name="ai_runs_status_check",
        ),
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
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AI_RUN_STATUS_SUCCESS,
    )
    # Store provider/error details when status is failed.
    error_message: Mapped[str | None] = mapped_column(Text)

    session: Mapped["ChatSession"] = relationship(back_populates="ai_runs")
