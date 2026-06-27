import asyncio
import sys
from pathlib import Path

from sqlalchemy import text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.db.session import AsyncSessionLocal


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

    print(f"vector_available={available}")
    print(f"vector_installed={installed}")
    print(f"embedding_vector_column={has_vector_column}")


if __name__ == "__main__":
    try:
        asyncio.run(check_pgvector())
    except Exception as exc:
        print("pgvector check FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
