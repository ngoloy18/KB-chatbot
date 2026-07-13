import asyncio
import sys
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select

# Add the project root to Python's import path when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.constants.auth import USER_ROLE_ADMIN, USER_ROLE_USER
from app.constants.permissions import DOCUMENT_PERMISSION_READ
from app.core.config import DocumentCategory, settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.database import Document, DocumentPermission, User
from app.repositories.documents.documents import (
    DocumentChunkPayload,
    document_repository,
)
from app.repositories.users.users import user_repository
from app.schemas.documents.schemas import DocumentCreate, DocumentUpdate
from app.services import document_service
from app.services.documents.exceptions import DocumentAccessDeniedError


TEST_EMBEDDING = [1.0] + [0.0] * 3071


async def create_test_user(db, email: str, *, is_admin: bool = False) -> User:
    """Create one verified user for the global document access test."""

    return await user_repository.create_user(
        db=db,
        email=email,
        hashed_password=hash_password("Password123!"),
        role=USER_ROLE_ADMIN if is_admin else USER_ROLE_USER,
        is_email_verified=True,
    )


async def create_test_document(
    db,
    *,
    name: str,
    content: str,
    current_user_id: UUID,
    is_admin: bool,
):
    """Create one ready document through the service."""

    return await document_service.create_document(
        db=db,
        payload=DocumentCreate(
            name=name,
            category=DocumentCategory.API_STANDARD,
            content=content,
            file_name=f"{name}.md",
            file_path=f"uploads/{name}.md",
            file_type="text/markdown",
        ),
        current_user_id=current_user_id,
        is_admin=is_admin,
    )


async def assert_global_document_access(
    db,
    *,
    document_id: UUID,
    document_name: str,
    unique_phrase: str,
    user_id: UUID,
) -> None:
    """Verify every read surface exposes an admin document to a normal user."""

    documents = await document_service.list_documents(
        db=db,
        name=document_name,
        current_user_id=user_id,
        is_admin=False,
    )
    if documents.total != 1 or documents.items[0].id != document_id:
        raise AssertionError("Normal users should list global admin documents.")

    document = await document_service.get_document(
        db=db,
        document_id=document_id,
        current_user_id=user_id,
        is_admin=False,
    )
    if document.id != document_id or not document.is_global_read:
        raise AssertionError("Normal users should read global admin documents.")

    context_documents = await document_repository.list_documents_for_context(
        db=db,
        categories=[DocumentCategory.API_STANDARD],
        user_id=user_id,
        include_all=False,
    )
    if document_id not in {item.id for item in context_documents}:
        raise AssertionError("Chat context should include global admin documents.")

    search_results = await document_service.search_document_chunks(
        db=db,
        query=unique_phrase,
        current_user_id=user_id,
        is_admin=False,
    )
    if (
        search_results.total != 1
        or search_results.items[0].document_id != document_id
    ):
        raise AssertionError("Normal users should search global admin document chunks.")

    versions = await document_service.list_document_versions(
        db=db,
        document_id=document_id,
        current_user_id=user_id,
        is_admin=False,
    )
    if versions.total != 1 or versions.items[0].document_id != document_id:
        raise AssertionError("Normal users should read global document versions.")

    semantic_matches = await document_repository.search_document_chunks_by_embedding(
        db=db,
        query_embedding=TEST_EMBEDDING,
        embedding_provider="global-read-test",
        embedding_model="global-read-test-model",
        top_k=5,
        min_similarity=0.9,
        user_id=user_id,
        include_all=False,
    )
    if document_id not in {match.document.id for match in semantic_matches}:
        raise AssertionError("Vector retrieval should include global admin documents.")

    try:
        await document_service.update_document(
            db=db,
            document_id=document_id,
            payload=DocumentUpdate(name=f"{document_name}-forbidden"),
            current_user_id=user_id,
            is_admin=False,
        )
    except DocumentAccessDeniedError:
        pass
    else:
        raise AssertionError("Global read access must not grant write access.")

    try:
        await document_service.delete_document(
            db=db,
            document_id=document_id,
            current_user_id=user_id,
            is_admin=False,
        )
    except DocumentAccessDeniedError:
        pass
    else:
        raise AssertionError("Global read access must not grant owner access.")


async def assert_private_document_hidden(
    db,
    *,
    document_id: UUID,
    document_name: str,
    unique_phrase: str,
    user_id: UUID,
) -> None:
    """Verify a different normal user cannot discover or read a private upload."""

    documents = await document_service.list_documents(
        db=db,
        name=document_name,
        current_user_id=user_id,
        is_admin=False,
    )
    if documents.total != 0:
        raise AssertionError("Other users should not list private user uploads.")

    search_results = await document_service.search_document_chunks(
        db=db,
        query=unique_phrase,
        current_user_id=user_id,
        is_admin=False,
    )
    if search_results.total != 0:
        raise AssertionError("Other users should not search private user uploads.")

    try:
        await document_service.get_document(
            db=db,
            document_id=document_id,
            current_user_id=user_id,
            is_admin=False,
        )
    except DocumentAccessDeniedError:
        pass
    else:
        raise AssertionError("Other users should not read private user uploads.")

    try:
        await document_service.list_document_versions(
            db=db,
            document_id=document_id,
            current_user_id=user_id,
            is_admin=False,
        )
    except DocumentAccessDeniedError:
        pass
    else:
        raise AssertionError("Other users should not read private document versions.")


async def check_admin_document_global_access() -> None:
    """Admin uploads should be readable by every current and future user."""

    original_embeddings_enabled = settings.embeddings_enabled
    settings.embeddings_enabled = False
    suffix = uuid4().hex[:8]
    admin_email = f"global_admin_{suffix}@example.com"
    existing_user_email = f"global_existing_{suffix}@example.com"
    future_user_email = f"global_future_{suffix}@example.com"
    global_document_name = f"global-admin-{suffix}"
    private_document_name = f"global-private-{suffix}"
    global_phrase = f"global-read-marker-{suffix}"
    private_phrase = f"private-owner-marker-{suffix}"

    async with AsyncSessionLocal() as db:
        try:
            admin = await create_test_user(db, admin_email, is_admin=True)
            existing_user = await create_test_user(db, existing_user_email)

            global_content = f"Admin knowledge containing {global_phrase}."
            global_document = await create_test_document(
                db,
                name=global_document_name,
                content=global_content,
                current_user_id=admin.id,
                is_admin=True,
            )
            stored_global_document = await db.scalar(
                select(Document).where(Document.id == global_document.id)
            )
            if (
                stored_global_document is None
                or not stored_global_document.is_global_read
            ):
                raise AssertionError("Admin uploads should be marked for global read.")
            await document_repository.replace_document_chunks(
                db=db,
                document=stored_global_document,
                chunks=[
                    DocumentChunkPayload(
                        chunk_index=0,
                        content=global_content,
                        token_count=len(global_content.split()),
                        embedding=TEST_EMBEDDING,
                        embedding_provider="global-read-test",
                        embedding_model="global-read-test-model",
                    )
                ],
            )
            await db.commit()

            private_document = await create_test_document(
                db,
                name=private_document_name,
                content=f"Private user knowledge containing {private_phrase}.",
                current_user_id=existing_user.id,
                is_admin=False,
            )
            stored_private_document = await db.scalar(
                select(Document).where(Document.id == private_document.id)
            )
            if stored_private_document is None or stored_private_document.is_global_read:
                raise AssertionError("Normal user uploads should remain private.")

            await assert_global_document_access(
                db,
                document_id=global_document.id,
                document_name=global_document_name,
                unique_phrase=global_phrase,
                user_id=existing_user.id,
            )

            future_user = await create_test_user(db, future_user_email)
            await assert_global_document_access(
                db,
                document_id=global_document.id,
                document_name=global_document_name,
                unique_phrase=global_phrase,
                user_id=future_user.id,
            )
            await assert_private_document_hidden(
                db,
                document_id=private_document.id,
                document_name=private_document_name,
                unique_phrase=private_phrase,
                user_id=future_user.id,
            )

            read_permission_count = await db.scalar(
                select(func.count())
                .select_from(DocumentPermission)
                .where(
                    DocumentPermission.document_id == global_document.id,
                    DocumentPermission.permission == DOCUMENT_PERMISSION_READ,
                )
            )
            if read_permission_count != 0:
                raise AssertionError(
                    "Global read access should not create per-user READ rows."
                )
        finally:
            settings.embeddings_enabled = original_embeddings_enabled
            await db.rollback()
            await db.execute(
                delete(Document).where(
                    Document.title.in_([global_document_name, private_document_name])
                )
            )
            await db.execute(
                delete(User).where(
                    User.email.in_(
                        [admin_email, existing_user_email, future_user_email]
                    )
                )
            )
            await db.commit()

    print("Admin document global access OK.")


if __name__ == "__main__":
    try:
        asyncio.run(check_admin_document_global_access())
    except Exception as exc:
        print("Admin document global access test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
