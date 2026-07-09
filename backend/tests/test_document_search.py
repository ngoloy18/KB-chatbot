import asyncio
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete

# Add the project root to Python's import path when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.constants.permissions import DOCUMENT_PERMISSION_READ
from app.core.config import DocumentCategory, settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.database import Document, User
from app.repositories.documents.documents import document_repository
from app.repositories.users.users import user_repository
from app.schemas.documents.schemas import (
    DocumentCreate,
    DocumentPermissionUpsertRequest,
    DocumentPermissionValue,
)
from app.services import document_service
from app.services.documents.exceptions import DocumentAccessDeniedError


async def check_document_chunk_search() -> None:
    """Verify chunk search respects admin/user document permissions."""

    original_embeddings_enabled = settings.embeddings_enabled
    settings.embeddings_enabled = False
    suffix = uuid4().hex[:8]
    document_name = f"search-test-{suffix}"
    private_document_name = f"search-private-{suffix}"
    user_email = f"search_user_{suffix}@example.com"
    other_user_email = f"search_other_{suffix}@example.com"
    unique_phrase = f"phoenix-search-{suffix}"
    private_phrase = f"owner-private-marker-{suffix}"

    async with AsyncSessionLocal() as db:
        try:
            user = await user_repository.create_user(
                db=db,
                email=user_email,
                hashed_password=hash_password("Password123!"),
                is_email_verified=True,
            )
            other_user = await user_repository.create_user(
                db=db,
                email=other_user_email,
                hashed_password=hash_password("Password123!"),
                is_email_verified=True,
            )
            document = await document_service.create_document(
                db,
                DocumentCreate(
                    name=document_name,
                    category=DocumentCategory.API_STANDARD,
                    content=(
                        "This API standard document contains a unique phrase: "
                        f"{unique_phrase}."
                    ),
                    file_name="search-test.md",
                    file_path="uploads/search-test.md",
                    file_type="text/markdown",
                ),
            )
            private_document = await document_service.create_document(
                db=db,
                payload=DocumentCreate(
                    name=private_document_name,
                    category=DocumentCategory.API_STANDARD,
                    content=(
                        "This user-owned document contains a unique phrase: "
                        f"{private_phrase}."
                    ),
                    file_name="search-private.md",
                    file_path="uploads/search-private.md",
                    file_type="text/markdown",
                ),
                current_user_id=user.id,
            )

            admin_results = await document_service.search_document_chunks(
                db=db,
                query=unique_phrase,
                is_admin=True,
            )
            if admin_results.total != 1:
                raise AssertionError(
                    f"Admin should find the matching chunk, got {admin_results.total}."
                )

            user_results_before_permission = await document_service.search_document_chunks(
                db=db,
                query=unique_phrase,
                current_user_id=user.id,
                is_admin=False,
            )
            if user_results_before_permission.total != 0:
                raise AssertionError("User should not search unpermitted documents.")

            await document_service.grant_document_permission(
                db=db,
                document_id=document.id,
                payload=DocumentPermissionUpsertRequest(
                    user_id=user.id,
                    permission=DocumentPermissionValue(DOCUMENT_PERMISSION_READ),
                ),
            )
            user_results_after_permission = await document_service.search_document_chunks(
                db=db,
                query=unique_phrase,
                current_user_id=user.id,
                is_admin=False,
            )
            if user_results_after_permission.total != 1:
                raise AssertionError("User should find chunks after read permission.")

            await document_service.revoke_document_permission(
                db=db,
                document_id=document.id,
                user_id=user.id,
            )
            user_results_after_revoke = await document_service.search_document_chunks(
                db=db,
                query=unique_phrase,
                current_user_id=user.id,
                is_admin=False,
            )
            if user_results_after_revoke.total != 0:
                raise AssertionError("User search should respect revoked permission.")

            owner_list = await document_service.list_documents(
                db=db,
                name=private_document_name,
                current_user_id=user.id,
                is_admin=False,
            )
            if owner_list.total != 1:
                raise AssertionError("Uploader should list their own private document.")
            await document_service.get_document(
                db=db,
                document_id=private_document.id,
                current_user_id=user.id,
                is_admin=False,
            )
            owner_search = await document_service.search_document_chunks(
                db=db,
                query=private_phrase,
                current_user_id=user.id,
                is_admin=False,
            )
            if owner_search.total != 1:
                raise AssertionError("Uploader should search their own chunks.")

            other_user_list = await document_service.list_documents(
                db=db,
                name=private_document_name,
                current_user_id=other_user.id,
                is_admin=False,
            )
            if other_user_list.total != 0:
                raise AssertionError("Other users should not list private uploads.")
            other_user_search = await document_service.search_document_chunks(
                db=db,
                query=private_phrase,
                current_user_id=other_user.id,
                is_admin=False,
            )
            if other_user_search.total != 0:
                raise AssertionError("Other users should not search private chunks.")
            try:
                await document_service.get_document(
                    db=db,
                    document_id=private_document.id,
                    current_user_id=other_user.id,
                    is_admin=False,
                )
            except DocumentAccessDeniedError:
                pass
            else:
                raise AssertionError("Other users should not read private uploads.")
        finally:
            settings.embeddings_enabled = original_embeddings_enabled
            await db.execute(
                delete(Document).where(
                    Document.title.in_([document_name, private_document_name])
                )
            )
            await db.execute(
                delete(User).where(User.email.in_([user_email, other_user_email]))
            )
            await db.commit()

    print("Document chunk search OK.")


if __name__ == "__main__":
    try:
        asyncio.run(check_document_chunk_search())
    except Exception as exc:
        print("Document chunk search test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
