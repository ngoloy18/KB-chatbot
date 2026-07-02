import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.constants.documents import DOCUMENT_STATUS_READY
from app.db.session import AsyncSessionLocal
from app.models.database import Document
from app.services import document_service


async def rechunk_documents(
    document_id: UUID | None = None,
    limit: int | None = None,
) -> None:
    """Recreate stored chunks and embeddings using the current chunking rules."""

    async with AsyncSessionLocal() as db:
        query = (
            select(Document)
            .options(selectinload(Document.category))
            .where(Document.status == DOCUMENT_STATUS_READY)
            .where(Document.is_deleted.is_(False))
            .order_by(Document.updated_at.desc())
        )
        if document_id is not None:
            query = query.where(Document.id == document_id)
        if limit is not None:
            query = query.limit(limit)

        documents = list((await db.scalars(query)).all())
        for document in documents:
            await document_service._replace_document_chunks(
                db=db,
                document=document,
                content=document.content,
            )
            print(f"Reprocessed {document.id} - {document.title}")

    print(f"Document rechunk OK: {len(documents)} document(s) reprocessed.")


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""

    parser = argparse.ArgumentParser(
        description="Recreate document chunks and embeddings."
    )
    parser.add_argument(
        "--document-id",
        type=UUID,
        default=None,
        help="Only reprocess one document UUID.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of ready documents to reprocess.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        args = parse_args()
        asyncio.run(
            rechunk_documents(
                document_id=args.document_id,
                limit=args.limit,
            )
        )
    except Exception as exc:
        print("Document rechunk FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
