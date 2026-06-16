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


# All application-owned tables live in the PostgreSQL schema named "kb".
# Keeping the schema name in one constant prevents typo bugs in table mappings.
SCHEMA_NAME = "kb"


class TimestampMixin:
    """Reusable created_at/updated_at columns shared by most database tables."""

    # server_default lets PostgreSQL fill the creation time when a row is inserted.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    # onupdate tells SQLAlchemy to update this value when the row changes.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


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

    # Relationships let SQLAlchemy navigate from one user to related records.
    documents: Mapped[list["Document"]] = relationship(back_populates="creator")
    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user")
    document_permissions: Mapped[list["DocumentPermission"]] = relationship(
        back_populates="user"
    )


class DocumentCategoryModel(TimestampMixin, Base):
    """One of the six knowledge-base categories that documents can belong to."""

    __tablename__ = "document_categories"
    __table_args__ = {"schema": SCHEMA_NAME}

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    # This stores values such as "database" or "coding-convention".
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    documents: Mapped[list["Document"]] = relationship(back_populates="category")


class Document(TimestampMixin, Base):
    """Uploaded knowledge-base document stored for AI retrieval and CRUD APIs."""

    __tablename__ = "documents"
    __table_args__ = (
        # Status describes where the document is in the upload/processing pipeline.
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
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="uploaded")
    # Nullable until authentication is implemented and every request has a user.
    created_by: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey(f"{SCHEMA_NAME}.users.id"),
    )

    # Relationships connect this document to category, owner, chunks, and sources.
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
        """Return the category as the existing Python enum type."""

        return DocumentCategory(self.category.name)


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

    document: Mapped[Document] = relationship(back_populates="chunks")
    message_sources: Mapped[list["MessageSource"]] = relationship(back_populates="chunk")


class DocumentPermission(TimestampMixin, Base):
    """Per-user access rule for a document."""

    __tablename__ = "document_permissions"
    __table_args__ = (
        # Keep permission values predictable for authorization checks.
        CheckConstraint(
            "permission IN ('read', 'write', 'owner')",
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

    document: Mapped[Document] = relationship(back_populates="permissions")
    user: Mapped[User] = relationship(back_populates="document_permissions")


class ChatSession(TimestampMixin, Base):
    """One conversation thread owned by a user."""

    __tablename__ = "chat_sessions"
    __table_args__ = {"schema": SCHEMA_NAME}

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        # Deleting a user removes that user's chat sessions.
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
    """One message in a chat session from the user, assistant, or system."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        # Role tells the app how to interpret this message in the conversation.
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

    message: Mapped[ChatMessage] = relationship(back_populates="sources")
    document: Mapped[Document] = relationship(back_populates="message_sources")
    chunk: Mapped[DocumentChunk | None] = relationship(back_populates="message_sources")


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

    session: Mapped[ChatSession] = relationship(back_populates="ai_runs")
