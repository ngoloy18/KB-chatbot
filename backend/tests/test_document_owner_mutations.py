import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.repositories.documents.documents import document_repository
from app.services import document_service
from app.services.documents.exceptions import DocumentAccessDeniedError


async def expect_access_denied(awaitable, message: str) -> None:
    """Assert that a document mutation is rejected."""

    try:
        await awaitable
    except DocumentAccessDeniedError:
        return
    raise AssertionError(message)


async def check_document_owner_mutations() -> None:
    """Verify admins can read user documents but cannot mutate them as owners."""

    owner_id = uuid4()
    admin_id = uuid4()
    document = SimpleNamespace(
        id=uuid4(),
        created_by=owner_id,
        content_checksum=None,
    )

    original_get = document_service._get_document_or_raise
    original_soft_delete = document_repository.soft_delete_document
    original_restore = document_repository.restore_document
    document_service._get_document_or_raise = AsyncMock(return_value=document)
    document_repository.soft_delete_document = AsyncMock()
    document_repository.restore_document = AsyncMock()
    try:
        await expect_access_denied(
            document_service._raise_if_cannot_update_document(
                db=SimpleNamespace(),
                document_id=document.id,
                current_user_id=admin_id,
                is_admin=True,
            ),
            "An admin must not update a document uploaded by another user.",
        )
        await expect_access_denied(
            document_service.delete_document(
                db=SimpleNamespace(),
                document_id=document.id,
                current_user_id=admin_id,
                is_admin=True,
            ),
            "An admin must not delete a document uploaded by another user.",
        )
        await expect_access_denied(
            document_service.restore_document(
                db=SimpleNamespace(),
                document_id=document.id,
                current_user_id=admin_id,
                is_admin=True,
            ),
            "An admin must not restore a document uploaded by another user.",
        )

        await document_service._raise_if_cannot_update_document(
            db=SimpleNamespace(),
            document_id=document.id,
            current_user_id=owner_id,
            is_admin=False,
        )
        await document_service.delete_document(
            db=SimpleNamespace(),
            document_id=document.id,
            current_user_id=owner_id,
            is_admin=False,
        )
        document_repository.soft_delete_document.assert_awaited_once()
    finally:
        document_service._get_document_or_raise = original_get
        document_repository.soft_delete_document = original_soft_delete
        document_repository.restore_document = original_restore

    print("Document owner-only mutations OK.")


if __name__ == "__main__":
    asyncio.run(check_document_owner_mutations())
