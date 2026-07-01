"""initial kb schema

Revision ID: 0001_initial_kb_schema
Revises:
Create Date: 2026-06-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.config import settings


revision: str = "0001_initial_kb_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Use the same schema setting as the SQLAlchemy models so new environments can
# choose their own schema name without editing migration code.
SCHEMA = settings.database_schema


def upgrade() -> None:
    """Create the initial database structure for the knowledge-base chatbot."""

    # Create the app schema first because every table below lives inside it.
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    # pgcrypto provides gen_random_uuid(), used by UUID primary key defaults.
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # Users are created first because documents and chat sessions can reference them.
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.Text(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('admin', 'user')", name="users_role_check"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        schema=SCHEMA,
    )

    # Categories are seed data for the six knowledge-base standards.
    op.create_table(
        "document_categories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        schema=SCHEMA,
    )

    # Insert the six categories the API enum accepts.
    op.bulk_insert(
        sa.table(
            "document_categories",
            sa.column("name", sa.String),
            sa.column("description", sa.Text),
            schema=SCHEMA,
        ),
        [
            {
                "name": "coding-convention",
                "description": "Coding standards and style rules",
            },
            {
                "name": "git-flow",
                "description": "Git branching, commits, and workflow rules",
            },
            {
                "name": "pull-request",
                "description": "Pull request process and review rules",
            },
            {
                "name": "database",
                "description": "Database design, migrations, and query rules",
            },
            {
                "name": "api-standard",
                "description": "API design and response standards",
            },
            {
                "name": "logging",
                "description": "Logging, monitoring, and debugging standards",
            },
        ],
    )

    # Documents store uploaded text, file metadata, category, and future owner.
    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("file_type", sa.String(length=50), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('uploaded', 'processing', 'ready', 'failed')",
            name="documents_status_check",
        ),
        sa.ForeignKeyConstraint(["category_id"], [f"{SCHEMA}.document_categories.id"]),
        sa.ForeignKeyConstraint(["created_by"], [f"{SCHEMA}.users.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )

    # Chunks are smaller pieces of a document for future AI retrieval/vector search.
    op.create_table(
        "document_chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("embedding_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            [f"{SCHEMA}.documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="document_chunks_unique_index",
        ),
        schema=SCHEMA,
    )

    # Permissions control which normal users can read/write/own each document.
    op.create_table(
        "document_permissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "permission IN ('read', 'write', 'owner')",
            name="document_permissions_permission_check",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            [f"{SCHEMA}.documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            [f"{SCHEMA}.users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "user_id",
            name="document_permissions_unique_user_document",
        ),
        schema=SCHEMA,
    )

    # A chat session is one conversation thread owned by a user.
    op.create_table(
        "chat_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            [f"{SCHEMA}.users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )

    # Chat messages are the user/assistant/system messages in a session.
    op.create_table(
        "chat_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="chat_messages_role_check",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            [f"{SCHEMA}.chat_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )

    # Message sources connect an AI answer to the document/chunk it used.
    op.create_table(
        "message_sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            [f"{SCHEMA}.document_chunks.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            [f"{SCHEMA}.documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            [f"{SCHEMA}.chat_messages.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )

    # AI runs keep metadata about each model call for debugging and token tracking.
    op.create_table(
        "ai_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assistant_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=True, server_default="0"),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="success",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('success', 'failed')",
            name="ai_runs_status_check",
        ),
        sa.ForeignKeyConstraint(
            ["assistant_message_id"],
            [f"{SCHEMA}.chat_messages.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            [f"{SCHEMA}.chat_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_message_id"],
            [f"{SCHEMA}.chat_messages.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )

    # Indexes speed up common lookups on foreign-key/filter columns.
    op.create_index("idx_documents_category_id", "documents", ["category_id"], schema=SCHEMA)
    op.create_index("idx_documents_created_by", "documents", ["created_by"], schema=SCHEMA)
    op.create_index(
        "idx_document_chunks_document_id",
        "document_chunks",
        ["document_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "idx_document_permissions_user_id",
        "document_permissions",
        ["user_id"],
        schema=SCHEMA,
    )
    op.create_index("idx_chat_sessions_user_id", "chat_sessions", ["user_id"], schema=SCHEMA)
    op.create_index(
        "idx_chat_messages_session_id",
        "chat_messages",
        ["session_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "idx_message_sources_message_id",
        "message_sources",
        ["message_id"],
        schema=SCHEMA,
    )
    op.create_index("idx_ai_runs_session_id", "ai_runs", ["session_id"], schema=SCHEMA)


def downgrade() -> None:
    """Remove the initial schema objects in reverse dependency order."""

    # Drop indexes before dropping their tables.
    op.drop_index("idx_ai_runs_session_id", table_name="ai_runs", schema=SCHEMA)
    op.drop_index("idx_message_sources_message_id", table_name="message_sources", schema=SCHEMA)
    op.drop_index("idx_chat_messages_session_id", table_name="chat_messages", schema=SCHEMA)
    op.drop_index("idx_chat_sessions_user_id", table_name="chat_sessions", schema=SCHEMA)
    op.drop_index(
        "idx_document_permissions_user_id",
        table_name="document_permissions",
        schema=SCHEMA,
    )
    op.drop_index(
        "idx_document_chunks_document_id",
        table_name="document_chunks",
        schema=SCHEMA,
    )
    op.drop_index("idx_documents_created_by", table_name="documents", schema=SCHEMA)
    op.drop_index("idx_documents_category_id", table_name="documents", schema=SCHEMA)

    # Drop child tables before parent tables so foreign keys do not block removal.
    op.drop_table("ai_runs", schema=SCHEMA)
    op.drop_table("message_sources", schema=SCHEMA)
    op.drop_table("chat_messages", schema=SCHEMA)
    op.drop_table("chat_sessions", schema=SCHEMA)
    op.drop_table("document_permissions", schema=SCHEMA)
    op.drop_table("document_chunks", schema=SCHEMA)
    op.drop_table("documents", schema=SCHEMA)
    op.drop_table("document_categories", schema=SCHEMA)
    op.drop_table("users", schema=SCHEMA)
