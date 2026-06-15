from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import DocumentCategory
from app.db.base import Base


SCHEMA_NAME = "kb"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'user')", name="users_role_check"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    documents: Mapped[list["Document"]] = relationship(back_populates="creator")
    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user")
    document_permissions: Mapped[list["DocumentPermission"]] = relationship(
        back_populates="user"
    )


class DocumentCategoryModel(TimestampMixin, Base):
    __tablename__ = "document_categories"
    __table_args__ = {"schema": SCHEMA_NAME}

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    documents: Mapped[list["Document"]] = relationship(back_populates="category")


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded', 'processing', 'ready', 'failed')",
            name="documents_status_check",
        ),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    category_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey(f"{SCHEMA_NAME}.document_categories.id"),
        nullable=False,
    )
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_path: Mapped[str | None] = mapped_column(Text)
    file_type: Mapped[str | None] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="uploaded")
    created_by: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey(f"{SCHEMA_NAME}.users.id"),
    )

    category: Mapped[DocumentCategoryModel] = relationship(back_populates="documents")
    creator: Mapped[User | None] = relationship(back_populates="documents")
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
        return DocumentCategory(self.category.name)


class DocumentChunk(TimestampMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
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
        ForeignKey(f"{SCHEMA_NAME}.documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    embedding_id: Mapped[str | None] = mapped_column(Text)

    document: Mapped[Document] = relationship(back_populates="chunks")
    message_sources: Mapped[list["MessageSource"]] = relationship(back_populates="chunk")


class DocumentPermission(TimestampMixin, Base):
    __tablename__ = "document_permissions"
    __table_args__ = (
        CheckConstraint(
            "permission IN ('read', 'write', 'owner')",
            name="document_permissions_permission_check",
        ),
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

    document: Mapped[Document] = relationship(back_populates="permissions")
    user: Mapped[User] = relationship(back_populates="document_permissions")


class ChatSession(TimestampMixin, Base):
    __tablename__ = "chat_sessions"
    __table_args__ = {"schema": SCHEMA_NAME}

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey(f"{SCHEMA_NAME}.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(255))

    user: Mapped[User] = relationship(back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    ai_runs: Mapped[list["AIRun"]] = relationship(back_populates="session")


class ChatMessage(TimestampMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
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

    session: Mapped[ChatSession] = relationship(back_populates="messages")
    sources: Mapped[list["MessageSource"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
    )


class MessageSource(TimestampMixin, Base):
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
        ForeignKey(f"{SCHEMA_NAME}.document_chunks.id", ondelete="SET NULL"),
    )
    similarity_score: Mapped[float | None] = mapped_column(Float)

    message: Mapped[ChatMessage] = relationship(back_populates="sources")
    document: Mapped[Document] = relationship(back_populates="message_sources")
    chunk: Mapped[DocumentChunk | None] = relationship(back_populates="message_sources")


class AIRun(TimestampMixin, Base):
    __tablename__ = "ai_runs"
    __table_args__ = (
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
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    error_message: Mapped[str | None] = mapped_column(Text)

    session: Mapped[ChatSession] = relationship(back_populates="ai_runs")
