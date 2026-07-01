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


async def check_document_chunk_search() -> None:
    """Verify chunk search respects admin/user document permissions."""

    original_embeddings_enabled = settings.embeddings_enabled
    settings.embeddings_enabled = False
    suffix = uuid4().hex[:8]
    document_name = f"search-test-{suffix}"
    user_email = f"search_user_{suffix}@example.com"
    unique_phrase = f"phoenix-search-{suffix}"

    async with AsyncSessionLocal() as db:
        try:
            user = await user_repository.create_user(
                db=db,
                email=user_email,
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

            admin_results = await document_service.search_document_chunks(
                db=db,
                query=unique_phrase,
                is_admin=True,
            )
            if admin_results.total != 1:
                raise AssertionError("Admin should find the matching chunk.")

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
        finally:
            settings.embeddings_enabled = original_embeddings_enabled
            await db.execute(delete(Document).where(Document.title == document_name))
            await db.execute(delete(User).where(User.email == user_email))
            await db.commit()

    print("Document chunk search OK.")


if __name__ == "__main__":
    try:
        asyncio.run(check_document_chunk_search())
    except Exception as exc:
        print("Document chunk search test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
