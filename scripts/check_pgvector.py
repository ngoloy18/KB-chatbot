import asyncio
import sys
from pathlib import Path

from sqlalchemy import text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.db.session import AsyncSessionLocal


INDEX_NAME = "idx_document_chunks_embedding_vector_hnsw"


async def check_pgvector() -> None:
    """Verify whether the connected PostgreSQL database can use pgvector."""

    async with AsyncSessionLocal() as db:
        available = await db.scalar(
            text("SELECT count(1) FROM pg_available_extensions WHERE name = :name"),
            {"name": "vector"},
        )
        installed = await db.scalar(
            text("SELECT count(1) FROM pg_extension WHERE extname = :name"),
            {"name": "vector"},
        )
        if available:
            await db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await db.execute(
                text(
                    f"""
                    ALTER TABLE {settings.database_schema}.document_chunks
                    ADD COLUMN IF NOT EXISTS embedding_vector vector
                    """
                )
            )
            await db.execute(
                text(
                    f"""
                    UPDATE {settings.database_schema}.document_chunks
                    SET embedding_vector = CAST(embedding AS vector)
                    WHERE embedding IS NOT NULL
                      AND embedding_vector IS NULL
                    """
                )
            )
            await db.commit()
            installed = await db.scalar(
                text("SELECT count(1) FROM pg_extension WHERE extname = :name"),
                {"name": "vector"},
            )
            await ensure_embedding_index(db)
        has_vector_column = await db.scalar(
            text(
                """
                SELECT count(1)
                FROM information_schema.columns
                WHERE table_schema = :schema_name
                  AND table_name = 'document_chunks'
                  AND column_name = 'embedding_vector'
                """
            ),
            {"schema_name": settings.database_schema},
        )
        halfvec_available = await db.scalar(
            text("SELECT count(1) FROM pg_type WHERE typname = :name"),
            {"name": "halfvec"},
        )
        index_definition = await db.scalar(
            text(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = :schema_name
                  AND tablename = 'document_chunks'
                  AND indexname = :index_name
                """
            ),
            {"schema_name": settings.database_schema, "index_name": INDEX_NAME},
        )

    print(f"vector_available={available}")
    print(f"vector_installed={installed}")
    print(f"halfvec_available={halfvec_available}")
    print(f"embedding_vector_column={has_vector_column}")
    print(f"embedding_vector_index={1 if index_definition else 0}")
    if index_definition:
        print(f"embedding_vector_index_def={index_definition}")


async def ensure_embedding_index(db) -> None:
    """Create the best supported HNSW index for stored chunk embeddings."""

    configured_dimensions = settings.embedding_dimensions or "NULL"
    await db.execute(
        text(
            f"""
            DO $$
            DECLARE
                configured_dimensions integer := {configured_dimensions};
                vector_dimensions integer;
                distinct_dimension_count integer;
                halfvec_available boolean;
            BEGIN
                IF configured_dimensions IS NOT NULL THEN
                    vector_dimensions := configured_dimensions;
                ELSE
                    SELECT COUNT(DISTINCT embedding_dimensions)
                    INTO distinct_dimension_count
                    FROM {settings.database_schema}.document_chunks
                    WHERE embedding_dimensions IS NOT NULL;

                    IF distinct_dimension_count = 1 THEN
                        SELECT embedding_dimensions
                        INTO vector_dimensions
                        FROM {settings.database_schema}.document_chunks
                        WHERE embedding_dimensions IS NOT NULL
                        LIMIT 1;
                    END IF;
                END IF;

                IF vector_dimensions IS NULL OR vector_dimensions <= 0 THEN
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
                        '{settings.database_schema}',
                        vector_dimensions,
                        vector_dimensions
                    );
                    EXECUTE format(
                        'CREATE INDEX IF NOT EXISTS {INDEX_NAME} ON %I.document_chunks USING hnsw (embedding_vector vector_cosine_ops) WHERE embedding_vector IS NOT NULL',
                        '{settings.database_schema}'
                    );
                    RETURN;
                END IF;

                IF vector_dimensions <= 4000 AND halfvec_available THEN
                    EXECUTE format(
                        'CREATE INDEX IF NOT EXISTS {INDEX_NAME} ON %I.document_chunks USING hnsw ((embedding_vector::halfvec(%s)) halfvec_cosine_ops) WHERE embedding_vector IS NOT NULL',
                        '{settings.database_schema}',
                        vector_dimensions
                    );
                END IF;
            END
            $$;
            """
        )
    )
    await db.commit()


if __name__ == "__main__":
    try:
        asyncio.run(check_pgvector())
    except Exception as exc:
        print("pgvector check FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
