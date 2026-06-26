import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.constants.documents import DOCUMENT_STATUS_READY
from app.db.session import AsyncSessionLocal
from app.models.database import Document, DocumentChunk
from app.services.ai import EmbeddingDocument, create_embedding_provider


def serialize_embedding(embedding: list[float]) -> str:
    """Serialize embedding values for PostgreSQL storage."""

    return json.dumps([float(value) for value in embedding], separators=(",", ":"))


async def backfill_embeddings(limit: int | None = None) -> None:
    """Generate embeddings for existing ready document chunks."""

    embedding_provider = create_embedding_provider()
    async with AsyncSessionLocal() as db:
        query = (
            select(DocumentChunk, Document)
            .join(Document)
            .options(selectinload(Document.category))
            .where(Document.status == DOCUMENT_STATUS_READY)
            .where(Document.is_deleted.is_(False))
            .where(
                (DocumentChunk.embedding.is_(None))
                | (DocumentChunk.embedding_provider != embedding_provider.provider_name)
                | (DocumentChunk.embedding_model != embedding_provider.model_name)
            )
            .order_by(Document.updated_at.desc(), DocumentChunk.chunk_index.asc())
        )
        if limit is not None:
            query = query.limit(limit)
        rows = list((await db.execute(query)).all())
        updated = 0
        for chunk, document in rows:
            embeddings = await embedding_provider.embed_documents(
                [
                    EmbeddingDocument(
                        title=document.title,
                        content=chunk.content,
                    )
                ]
            )
            embedding = embeddings[0]
            chunk.embedding = serialize_embedding(embedding)
            chunk.embedding_provider = embedding_provider.provider_name
            chunk.embedding_model = embedding_provider.model_name
            chunk.embedding_dimensions = len(embedding)
            chunk.embedded_at = datetime.now(UTC)
            updated += 1
            await db.commit()

    print(
        "Embedding backfill OK: "
        f"{updated} chunk(s) stored for {embedding_provider.provider_name}/"
        f"{embedding_provider.model_name}."
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""

    parser = argparse.ArgumentParser(description="Backfill document chunk embeddings.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of chunks to embed in this run.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        args = parse_args()
        asyncio.run(backfill_embeddings(limit=args.limit))
    except Exception as exc:
        print("Embedding backfill FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
