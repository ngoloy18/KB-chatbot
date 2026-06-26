import asyncio
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete

# Add the project root to Python's import path when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import DocumentCategory
from app.db.session import AsyncSessionLocal
from app.models.database import Document
from app.schemas.documents.schemas import DocumentCreate, DocumentUpdate
from app.services import document_service
from app.services.documents.exceptions import (
    DocumentDuplicateError,
    DocumentNotFoundError,
)


async def check_document_lifecycle() -> None:
    """Verify version history, soft delete/restore, and duplicate detection."""

    suffix = uuid4().hex[:8]
    document_name = f"lifecycle-{suffix}"
    original_content = f"# Lifecycle {suffix}\n\nOriginal content {suffix}."
    updated_content = f"# Lifecycle {suffix}\n\nUpdated content {suffix}."

    async with AsyncSessionLocal() as db:
        try:
            document = await document_service.create_document(
                db,
                DocumentCreate(
                    name=document_name,
                    category=DocumentCategory.API_STANDARD,
                    content=original_content,
                    file_name=f"{document_name}.md",
                    file_path=f"uploads/{document_name}.md",
                    file_type="text/markdown",
                ),
            )
            if not document.content_checksum or len(document.content_checksum) != 64:
                raise AssertionError("Created document should have a SHA-256 checksum.")

            try:
                await document_service.create_document(
                    db,
                    DocumentCreate(
                        name=f"{document_name}-duplicate",
                        category=DocumentCategory.API_STANDARD,
                        content=original_content,
                        file_name=f"{document_name}-duplicate.md",
                        file_path=f"uploads/{document_name}-duplicate.md",
                        file_type="text/markdown",
                    ),
                )
            except DocumentDuplicateError:
                pass
            else:
                raise AssertionError("Duplicate active content should be rejected.")

            versions = await document_service.list_document_versions(
                db,
                document.id,
                is_admin=True,
            )
            if versions.total != 1 or versions.items[0].version_number != 1:
                raise AssertionError("Create should save version 1.")

            updated = await document_service.update_document(
                db,
                document.id,
                DocumentUpdate(
                    name=document_name,
                    category=DocumentCategory.API_STANDARD,
                    content=updated_content,
                    file_name=f"{document_name}-updated.md",
                    file_path=f"uploads/{document_name}-updated.md",
                    file_type="text/markdown",
                ),
                is_admin=True,
            )
            if updated.content_checksum == document.content_checksum:
                raise AssertionError("Updated content should change checksum.")

            versions = await document_service.list_document_versions(
                db,
                document.id,
                is_admin=True,
            )
            if versions.total != 2:
                raise AssertionError("Update should append a document version.")

            await document_service.delete_document(db, document.id, is_admin=True)
            try:
                await document_service.get_document(db, document.id, is_admin=True)
            except DocumentNotFoundError:
                pass
            else:
                raise AssertionError("Soft-deleted documents should be hidden from get.")

            restored = await document_service.restore_document(
                db,
                document.id,
                is_admin=True,
            )
            if restored.is_deleted or restored.deleted_at is not None:
                raise AssertionError("Restore should clear soft-delete fields.")
        finally:
            await db.execute(
                delete(Document).where(Document.title.ilike(f"{document_name}%"))
            )
            await db.commit()

    print("Document lifecycle OK.")


if __name__ == "__main__":
    try:
        asyncio.run(check_document_lifecycle())
    except Exception as exc:
        print("Document lifecycle test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
