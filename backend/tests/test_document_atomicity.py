import asyncio
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, func, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import DocumentCategory, settings
from app.db.session import AsyncSessionLocal
from app.models.database import (
    Document,
    DocumentChunk,
    DocumentPermission,
    DocumentVersion,
    User,
)
from app.repositories.documents.documents import document_repository
from app.repositories.users.users import user_repository
from app.schemas.documents.schemas import DocumentCreate, DocumentUpdate
from app.services import document_service


async def _fail_version_creation(*args: object, **kwargs: object) -> None:
    """Simulate a failure after document and chunk rows have been staged."""

    raise RuntimeError("injected document version failure")


async def check_create_is_atomic() -> None:
    """A version failure must not leave a document or its chunks behind."""

    document_name = f"atomic-create-{uuid4().hex[:8]}"
    user_email = f"atomic-create-{uuid4().hex}@example.com"
    original_create_version = document_repository.create_document_version
    document_repository.create_document_version = _fail_version_creation
    try:
        async with AsyncSessionLocal() as db:
            try:
                user = await user_repository.create_user(
                    db=db,
                    email=user_email,
                    hashed_password="test-only-password-hash",
                )
                user_id = user.id
                try:
                    await document_service.create_document(
                        db=db,
                        payload=DocumentCreate(
                            name=document_name,
                            category=DocumentCategory.DATABASE,
                            content=f"# Atomic create\n\n{uuid4().hex}",
                        ),
                        current_user_id=user_id,
                    )
                except RuntimeError as exc:
                    if str(exc) != "injected document version failure":
                        raise
                else:
                    raise AssertionError("Injected create failure should propagate.")

                document_count = await db.scalar(
                    select(func.count()).select_from(Document).where(
                        Document.title == document_name
                    )
                )
                if document_count != 0:
                    raise AssertionError("Failed create must roll back the document row.")

                permission_count = await db.scalar(
                    select(func.count()).select_from(DocumentPermission).where(
                        DocumentPermission.user_id == user_id
                    )
                )
                if permission_count != 0:
                    raise AssertionError(
                        "Failed create must roll back its owner permission."
                    )
            finally:
                await db.execute(delete(User).where(User.email == user_email))
                await db.commit()
    finally:
        document_repository.create_document_version = original_create_version


async def check_update_is_atomic() -> None:
    """A version failure must preserve the prior document and chunk state."""

    document_name = f"atomic-update-{uuid4().hex[:8]}"
    initial_content = f"# Original\n\nOriginal content {uuid4().hex}."
    updated_content = f"# Replacement\n\nReplacement content {uuid4().hex}."

    async with AsyncSessionLocal() as db:
        created = await document_service.create_document(
            db=db,
            payload=DocumentCreate(
                name=document_name,
                category=DocumentCategory.DATABASE,
                content=initial_content,
                file_name="original.md",
                file_path="uploads/original.md",
                file_type="text/markdown",
            ),
        )
        original_checksum = created.content_checksum
        original_chunks = [
            tuple(row)
            for row in (
                await db.execute(
                    select(DocumentChunk.chunk_index, DocumentChunk.content)
                    .where(DocumentChunk.document_id == created.id)
                    .order_by(DocumentChunk.chunk_index)
                )
            ).all()
        ]
        if not original_chunks:
            raise AssertionError("Atomic update setup should create document chunks.")

        original_create_version = document_repository.create_document_version
        document_repository.create_document_version = _fail_version_creation
        try:
            try:
                await document_service.update_document(
                    db=db,
                    document_id=created.id,
                    payload=DocumentUpdate(
                        name=f"{document_name}-replacement",
                        content=updated_content,
                        file_name="replacement.md",
                        file_path="uploads/replacement.md",
                    ),
                    is_admin=True,
                )
            except RuntimeError as exc:
                if str(exc) != "injected document version failure":
                    raise
            else:
                raise AssertionError("Injected update failure should propagate.")

            persisted_document = await db.scalar(
                select(Document).where(Document.id == created.id)
            )
            if persisted_document is None:
                raise AssertionError("Failed update must preserve the document row.")
            if persisted_document.title != document_name:
                raise AssertionError("Failed update must restore the previous title.")
            if persisted_document.content != initial_content:
                raise AssertionError("Failed update must restore the previous content.")
            if persisted_document.content_checksum != original_checksum:
                raise AssertionError("Failed update must restore the previous checksum.")
            if persisted_document.file_name != "original.md":
                raise AssertionError("Failed update must restore prior file metadata.")

            persisted_chunks = [
                tuple(row)
                for row in (
                    await db.execute(
                        select(DocumentChunk.chunk_index, DocumentChunk.content)
                        .where(DocumentChunk.document_id == created.id)
                        .order_by(DocumentChunk.chunk_index)
                    )
                ).all()
            ]
            if persisted_chunks != original_chunks:
                raise AssertionError(
                    "Failed update must restore the previous chunk indexes and content."
                )

            version_count = await db.scalar(
                select(func.count()).select_from(DocumentVersion).where(
                    DocumentVersion.document_id == created.id
                )
            )
            if version_count != 1:
                raise AssertionError("Failed update must not append a version.")
        finally:
            document_repository.create_document_version = original_create_version
            await db.execute(delete(Document).where(Document.id == created.id))
            await db.commit()


async def check_replacement_lookup_is_serialized() -> None:
    """A waiting replacement must observe the file path committed ahead of it."""

    document_name = f"serialized-update-{uuid4().hex[:8]}"
    original_path = f"uploads/{document_name}-original.md"
    first_replacement_path = f"uploads/{document_name}-first.md"

    async with AsyncSessionLocal() as setup_db:
        created = await document_service.create_document(
            db=setup_db,
            payload=DocumentCreate(
                name=document_name,
                category=DocumentCategory.DATABASE,
                content=f"# Original\n\n{uuid4().hex}",
                file_name="original.md",
                file_path=original_path,
                file_type="text/markdown",
            ),
        )
        document_id = created.id

    second_lookup = None
    try:
        async with AsyncSessionLocal() as first_db, AsyncSessionLocal() as second_db:
            first_old_path = (
                await document_service.get_document_file_path_for_replacement(
                    db=first_db,
                    document_id=document_id,
                    is_admin=True,
                )
            )
            if first_old_path != original_path:
                raise AssertionError("First replacement should see the original path.")

            second_lookup = asyncio.create_task(
                document_service.get_document_file_path_for_replacement(
                    db=second_db,
                    document_id=document_id,
                    is_admin=True,
                )
            )
            await asyncio.sleep(0.1)
            if second_lookup.done():
                raise AssertionError(
                    "Concurrent replacement lookup should wait for the row lock."
                )

            await document_service.update_document(
                db=first_db,
                document_id=document_id,
                payload=DocumentUpdate(
                    content=f"# First replacement\n\n{uuid4().hex}",
                    file_name="first.md",
                    file_path=first_replacement_path,
                ),
                is_admin=True,
            )

            second_old_path = await asyncio.wait_for(second_lookup, timeout=5)
            if second_old_path != first_replacement_path:
                raise AssertionError(
                    "Waiting replacement must see the preceding replacement path."
                )
            await second_db.rollback()
    finally:
        if second_lookup is not None and not second_lookup.done():
            second_lookup.cancel()
            await asyncio.gather(second_lookup, return_exceptions=True)
        async with AsyncSessionLocal() as cleanup_db:
            await cleanup_db.execute(
                delete(Document).where(Document.id == document_id)
            )
            await cleanup_db.commit()


async def main() -> None:
    """Run document transaction rollback checks."""

    original_embeddings_enabled = settings.embeddings_enabled
    settings.embeddings_enabled = False
    try:
        await check_create_is_atomic()
        await check_update_is_atomic()
        await check_replacement_lookup_is_serialized()
    finally:
        settings.embeddings_enabled = original_embeddings_enabled
    print("Document atomicity OK.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print("Document atomicity test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
