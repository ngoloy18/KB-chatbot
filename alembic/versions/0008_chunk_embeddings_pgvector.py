"""add pgvector embeddings for document chunks

Revision ID: 0008_chunk_embeddings_pgvector
Revises: 0007_document_lifecycle
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.config import settings


revision: str = "0008_chunk_embeddings_pgvector"
down_revision: str | None = "0007_document_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = settings.database_schema


def upgrade() -> None:
    """Enable pgvector and store embeddings on document chunks."""

    op.add_column(
        "document_chunks",
        sa.Column("embedding", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "document_chunks",
        sa.Column("embedding_provider", sa.String(length=50), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "document_chunks",
        sa.Column("embedding_model", sa.String(length=100), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "document_chunks",
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "document_chunks",
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_document_chunks_embedding_model",
        "document_chunks",
        ["embedding_provider", "embedding_model"],
        schema=SCHEMA,
    )
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_available_extensions
                WHERE name = 'vector'
            ) THEN
                CREATE EXTENSION IF NOT EXISTS vector;
                ALTER TABLE {SCHEMA}.document_chunks
                    ADD COLUMN IF NOT EXISTS embedding_vector vector;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Remove stored chunk embeddings."""

    op.drop_index(
        "idx_document_chunks_embedding_model",
        table_name="document_chunks",
        schema=SCHEMA,
    )
    op.drop_column("document_chunks", "embedded_at", schema=SCHEMA)
    op.drop_column("document_chunks", "embedding_dimensions", schema=SCHEMA)
    op.drop_column("document_chunks", "embedding_model", schema=SCHEMA)
    op.drop_column("document_chunks", "embedding_provider", schema=SCHEMA)
    op.execute(
        f"""
        ALTER TABLE {SCHEMA}.document_chunks
            DROP COLUMN IF EXISTS embedding_vector
        """
    )
    op.drop_column("document_chunks", "embedding", schema=SCHEMA)
