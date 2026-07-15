import asyncio
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete

# Add the project root to Python's import path when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import DocumentCategory, settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.database import Document, User
from app.repositories.users.users import user_repository
from app.schemas.documents.schemas import DocumentCreate, DocumentUpdate
from app.services import document_service
from app.services.documents.exceptions import (
    DocumentDuplicateError,
    DocumentNotFoundError,
)


def assert_no_public_file_path(payload: object) -> None:
    """Document API models must not expose local server storage paths."""

    if hasattr(payload, "model_dump") and "file_path" in payload.model_dump():
        raise AssertionError("Public document responses must not expose file_path.")


async def check_document_lifecycle() -> None:
    """Verify version history, soft delete/restore, and duplicate detection."""

    original_embeddings_enabled = settings.embeddings_enabled
    settings.embeddings_enabled = False
    suffix = uuid4().hex[:8]
    document_name = f"lifecycle-{suffix}"
    original_content = f"# Lifecycle {suffix}\n\nOriginal content {suffix}."
    updated_content = f"# Lifecycle {suffix}\n\nUpdated content {suffix}."

    async with AsyncSessionLocal() as db:
        owner = None
        try:
            owner = await user_repository.create_user(
                db,
                email=f"lifecycle-owner-{suffix}@example.com",
                full_name="Lifecycle Test Owner",
                hashed_password=hash_password("Password123!"),
            )
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
                current_user_id=owner.id,
            )
            if not document.content_checksum or len(document.content_checksum) != 64:
                raise AssertionError("Created document should have a SHA-256 checksum.")
            assert_no_public_file_path(document)

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
                    current_user_id=owner.id,
                )
            except DocumentDuplicateError:
                pass
            else:
                raise AssertionError("Duplicate active content should be rejected.")

            versions = await document_service.list_document_versions(
                db,
                document.id,
                current_user_id=owner.id,
            )
            if versions.total != 1 or versions.items[0].version_number != 1:
                raise AssertionError("Create should save version 1.")
            assert_no_public_file_path(versions.items[0])

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
                current_user_id=owner.id,
            )
            if updated.content_checksum == document.content_checksum:
                raise AssertionError("Updated content should change checksum.")
            assert_no_public_file_path(updated)

            versions = await document_service.list_document_versions(
                db,
                document.id,
                current_user_id=owner.id,
            )
            if versions.total != 2:
                raise AssertionError("Update should append a document version.")

            await document_service.delete_document(
                db,
                document.id,
                current_user_id=owner.id,
            )
            try:
                await document_service.get_document(db, document.id, is_admin=True)
            except DocumentNotFoundError:
                pass
            else:
                raise AssertionError("Soft-deleted documents should be hidden from get.")

            restored = await document_service.restore_document(
                db,
                document.id,
                current_user_id=owner.id,
            )
            if restored.is_deleted or restored.deleted_at is not None:
                raise AssertionError("Restore should clear soft-delete fields.")
            assert_no_public_file_path(restored)
        finally:
            settings.embeddings_enabled = original_embeddings_enabled
            await db.execute(
                delete(Document).where(Document.title.ilike(f"{document_name}%"))
            )
            if owner is not None:
                await db.execute(delete(User).where(User.id == owner.id))
            await db.commit()

    print("Document lifecycle OK.")


if __name__ == "__main__":
    try:
        asyncio.run(check_document_lifecycle())
    except Exception as exc:
        print("Document lifecycle test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
