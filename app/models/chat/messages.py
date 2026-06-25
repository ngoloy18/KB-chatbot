from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.constants_chat import (
    CHAT_ROLE_ASSISTANT,
    CHAT_ROLE_SYSTEM,
    CHAT_ROLE_USER,
)
from app.db.base import Base
from app.constants.constants_database import SCHEMA_NAME
from app.models.common.mixins import TimestampMixin


class ChatMessage(TimestampMixin, Base):
    """One message in a chat session from the user, assistant, or system."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        # Role tells the app how to interpret this message in the conversation.
        CheckConstraint(
            f"role IN ('{CHAT_ROLE_USER}', '{CHAT_ROLE_ASSISTANT}', '{CHAT_ROLE_SYSTEM}')",
            name="chat_messages_role_check",
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
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
    sources: Mapped[list["MessageSource"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
    )
