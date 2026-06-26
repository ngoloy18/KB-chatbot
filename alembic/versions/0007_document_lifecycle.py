"""add document lifecycle metadata

Revision ID: 0007_document_lifecycle
Revises: 0006_password_reset_tokens
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.config import settings


revision: str = "0007_document_lifecycle"
down_revision: str | None = "0006_password_reset_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = settings.database_schema


def upgrade() -> None:
    """Add document checksums, soft delete fields, and version history."""

    op.add_column(
        "documents",
        sa.Column("content_checksum", sa.String(length=64), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "documents",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "documents",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )

    op.execute(
        f"""
        UPDATE {SCHEMA}.documents
        SET content_checksum = encode(digest(content, 'sha256'), 'hex')
        WHERE content_checksum IS NULL
        """
    )

    op.create_index(
        "idx_documents_content_checksum",
        "documents",
        ["content_checksum"],
        schema=SCHEMA,
    )
    op.create_index(
        "idx_documents_is_deleted",
        "documents",
        ["is_deleted"],
        schema=SCHEMA,
    )

    op.create_table(
        "document_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("file_type", sa.String(length=50), nullable=True),
        sa.Column("content_checksum", sa.String(length=64), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["category_id"],
            [f"{SCHEMA}.document_categories.id"],
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            [f"{SCHEMA}.documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "version_number",
            name="document_versions_unique_document_version",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_document_versions_document_id",
        "document_versions",
        ["document_id"],
        schema=SCHEMA,
    )

    op.execute(
        f"""
        INSERT INTO {SCHEMA}.document_versions
            (
                document_id,
                version_number,
                title,
                category_id,
                file_name,
                file_path,
                file_type,
                content_checksum,
                content,
                created_at,
                updated_at
            )
        SELECT
            id,
            1,
            title,
            category_id,
            file_name,
            file_path,
            file_type,
            content_checksum,
            content,
            created_at,
            updated_at
        FROM {SCHEMA}.documents
        """
    )


def downgrade() -> None:
    """Remove document lifecycle metadata."""

    op.drop_index(
        "idx_document_versions_document_id",
        table_name="document_versions",
        schema=SCHEMA,
    )
    op.drop_table("document_versions", schema=SCHEMA)
    op.drop_index("idx_documents_is_deleted", table_name="documents", schema=SCHEMA)
    op.drop_index(
        "idx_documents_content_checksum",
        table_name="documents",
        schema=SCHEMA,
    )
    op.drop_column("documents", "deleted_at", schema=SCHEMA)
    op.drop_column("documents", "is_deleted", schema=SCHEMA)
    op.drop_column("documents", "content_checksum", schema=SCHEMA)
