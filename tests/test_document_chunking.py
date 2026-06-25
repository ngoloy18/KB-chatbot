import asyncio
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, func, select

# Add the project root to Python's import path when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import DocumentCategory
from app.db.session import AsyncSessionLocal
from app.models.database import Document, DocumentChunk
from app.schemas.documents.schemas import DocumentCreate, DocumentUpdate
from app.services import document_service
from app.services.documents.chunking import document_chunking_service


def check_text_chunking() -> None:
    """Verify the chunker splits long text into ordered chunks."""

    content = "\n\n".join(
        [
            "First paragraph about API standards.",
            "Second paragraph about database migrations.",
            "x" * 1400,
        ]
    )
    chunks = document_chunking_service.split_text(content, max_characters=500)
    if len(chunks) < 3:
        raise AssertionError("Long content should split into multiple chunks.")
    if [chunk.chunk_index for chunk in chunks] != list(range(len(chunks))):
        raise AssertionError("Chunk indexes should be sequential.")
    if any(not chunk.content for chunk in chunks):
        raise AssertionError("Chunks should not be empty.")
    if any(chunk.token_count < 1 for chunk in chunks):
        raise AssertionError("Chunks should include token counts.")


async def check_document_chunks_are_saved() -> None:
    """Verify document create/update writes rows into kb.document_chunks."""

    document_name = f"chunk-test-{uuid4().hex[:8]}"
    initial_content = "\n\n".join(
        f"Paragraph {index}: coding convention details." for index in range(80)
    )
    updated_content = "\n\n".join(
        f"Updated paragraph {index}: database migration details." for index in range(10)
    )

    async with AsyncSessionLocal() as db:
        try:
            created_document = await document_service.create_document(
                db,
                DocumentCreate(
                    name=document_name,
                    category=DocumentCategory.CODING_CONVENTION,
                    content=initial_content,
                    file_name="chunk-test.md",
                    file_path="uploads/chunk-test.md",
                    file_type="text/markdown",
                ),
            )
            initial_chunk_count = await db.scalar(
                select(func.count()).select_from(DocumentChunk).where(
                    DocumentChunk.document_id == created_document.id
                )
            )
            if not initial_chunk_count or initial_chunk_count < 2:
                raise AssertionError("Document create should save multiple chunks.")

            await document_service.update_document(
                db=db,
                document_id=created_document.id,
                payload=DocumentUpdate(content=updated_content),
                is_admin=True,
            )
            updated_chunk_count = await db.scalar(
                select(func.count()).select_from(DocumentChunk).where(
                    DocumentChunk.document_id == created_document.id
                )
            )
            expected_updated_chunks = len(
                document_chunking_service.split_text(updated_content)
            )
            if updated_chunk_count != expected_updated_chunks:
                raise AssertionError("Document update should replace old chunks.")
        finally:
            await db.execute(delete(Document).where(Document.title == document_name))
            await db.commit()


async def main() -> None:
    """Run document chunking checks."""

    check_text_chunking()
    await check_document_chunks_are_saved()
    print("Document chunking OK.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print("Document chunking test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
