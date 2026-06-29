"""add hnsw index for pgvector chunk search

Revision ID: 0009_pgvector_hnsw_index
Revises: 0008_chunk_embeddings_pgvector
Create Date: 2026-06-27
"""

from collections.abc import Sequence

from alembic import op

from app.core.config import settings


revision: str = "0009_pgvector_hnsw_index"
down_revision: str | None = "0008_chunk_embeddings_pgvector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = settings.database_schema
CONFIGURED_DIMENSIONS = settings.embedding_dimensions or "NULL"
INDEX_NAME = "idx_document_chunks_embedding_vector_hnsw"


def upgrade() -> None:
    """Create an HNSW cosine index when pgvector and dimensions are available."""

    op.execute(
        f"""
        DO $$
        DECLARE
            configured_dimensions integer := {CONFIGURED_DIMENSIONS};
            vector_dimensions integer;
            distinct_dimension_count integer;
            halfvec_available boolean;
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_available_extensions
                WHERE name = 'vector'
            ) THEN
                RAISE NOTICE 'pgvector is not available; skipping chunk vector index';
                RETURN;
            END IF;

            CREATE EXTENSION IF NOT EXISTS vector;

            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = '{SCHEMA}'
                  AND table_name = 'document_chunks'
                  AND column_name = 'embedding_vector'
            ) THEN
                RAISE NOTICE 'embedding_vector column is missing; skipping chunk vector index';
                RETURN;
            END IF;

            IF configured_dimensions IS NOT NULL THEN
                vector_dimensions := configured_dimensions;
            ELSE
                SELECT COUNT(DISTINCT embedding_dimensions)
                INTO distinct_dimension_count
                FROM {SCHEMA}.document_chunks
                WHERE embedding_dimensions IS NOT NULL;

                IF distinct_dimension_count = 1 THEN
                    SELECT embedding_dimensions
                    INTO vector_dimensions
                    FROM {SCHEMA}.document_chunks
                    WHERE embedding_dimensions IS NOT NULL
                    LIMIT 1;
                END IF;
            END IF;

            IF vector_dimensions IS NULL OR vector_dimensions <= 0 THEN
                RAISE NOTICE 'embedding dimensions are unknown; skipping chunk vector index';
                RETURN;
            END IF;

            SELECT EXISTS (
                SELECT 1
                FROM pg_type
                WHERE typname = 'halfvec'
            )
            INTO halfvec_available;

            IF vector_dimensions <= 2000 THEN
                EXECUTE format(
                    'ALTER TABLE %I.document_chunks ALTER COLUMN embedding_vector TYPE vector(%s) USING embedding_vector::vector(%s)',
                    '{SCHEMA}',
                    vector_dimensions,
                    vector_dimensions
                );

                EXECUTE format(
                    'CREATE INDEX IF NOT EXISTS {INDEX_NAME} ON %I.document_chunks USING hnsw (embedding_vector vector_cosine_ops) WHERE embedding_vector IS NOT NULL',
                    '{SCHEMA}'
                );
                RETURN;
            END IF;

            IF vector_dimensions <= 4000 AND halfvec_available THEN
                EXECUTE format(
                    'CREATE INDEX IF NOT EXISTS {INDEX_NAME} ON %I.document_chunks USING hnsw ((embedding_vector::halfvec(%s)) halfvec_cosine_ops) WHERE embedding_vector IS NOT NULL',
                    '{SCHEMA}',
                    vector_dimensions
                );
                RETURN;
            END IF;

            RAISE NOTICE 'embedding dimensions exceed index support; skipping chunk vector index';
        END
        $$;
        """
    )


def downgrade() -> None:
    """Drop the optional HNSW chunk vector index."""

    op.execute(
        f"""
        DROP INDEX IF EXISTS {SCHEMA}.{INDEX_NAME}
        """
    )
