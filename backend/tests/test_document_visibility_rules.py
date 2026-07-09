import asyncio
import sys
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import delete

# Add the project root to Python's import path when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.constants.auth import USER_ROLE_ADMIN
from app.core.config import DocumentCategory, settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.database import Document, User
from app.repositories.users.users import user_repository
from app.routes.documents.permissions import (
    grant_document_permission as grant_document_permission_route,
)
from app.routes.users.users import list_user_documents as list_user_documents_route
from app.schemas.documents.schemas import (
    DocumentCreate,
    DocumentPermissionUpsertRequest,
    DocumentPermissionValue,
)
from app.services import document_service
from app.services.documents.exceptions import (
    DocumentAccessConflictError,
    DocumentDuplicateError,
)


async def create_test_user(db, email: str) -> User:
    """Create one verified user for document visibility tests."""

    return await user_repository.create_user(
        db=db,
        email=email,
        hashed_password=hash_password("Password123!"),
        is_email_verified=True,
    )


async def create_test_admin(db, email: str) -> User:
    """Create one admin user for route-level permission checks."""

    return await user_repository.create_user(
        db=db,
        email=email,
        hashed_password=hash_password("Password123!"),
        role=USER_ROLE_ADMIN,
        is_email_verified=True,
    )


async def create_test_document(
    db,
    name: str,
    content: str,
    current_user_id: UUID | None = None,
):
    """Create a ready document through the service."""

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
    )


async def check_document_visibility_rules() -> None:
    """Verify per-user visible name and content duplicate rules."""

    original_embeddings_enabled = settings.embeddings_enabled
    settings.embeddings_enabled = False
    suffix = uuid4().hex[:8]
    name_prefix = f"visibility-{suffix}"
    admin_email = f"visibility_admin_{suffix}@example.com"
    user_email = f"visibility_user_{suffix}@example.com"
    other_user_email = f"visibility_other_{suffix}@example.com"

    async with AsyncSessionLocal() as db:
        try:
            admin = await create_test_admin(db, admin_email)
            user = await create_test_user(db, user_email)
            other_user = await create_test_user(db, other_user_email)

            first = await create_test_document(
                db=db,
                name=name_prefix,
                content=f"First visible content {suffix}.",
                current_user_id=user.id,
            )
            second = await create_test_document(
                db=db,
                name=name_prefix,
                content=f"Second visible content {suffix}.",
                current_user_id=user.id,
            )
            third = await create_test_document(
                db=db,
                name=name_prefix,
                content=f"Third visible content {suffix}.",
                current_user_id=user.id,
            )
            if [first.name, second.name, third.name] != [
                name_prefix,
                f"{name_prefix} (1)",
                f"{name_prefix} (2)",
            ]:
                raise AssertionError("Same-name visible uploads should be auto-renamed.")

            other_private = await create_test_document(
                db=db,
                name=name_prefix,
                content=f"Other user private content {suffix}.",
                current_user_id=other_user.id,
            )
            if other_private.name != name_prefix:
                raise AssertionError("Invisible documents should not affect display names.")

            try:
                await create_test_document(
                    db=db,
                    name=f"{name_prefix}-same-content",
                    content=first.content,
                    current_user_id=user.id,
                )
            except DocumentDuplicateError:
                pass
            else:
                raise AssertionError("Same-content visible uploads should be rejected.")

            shared_content = f"Shared duplicate access content {suffix}."
            admin_source = await create_test_document(
                db=db,
                name=f"{name_prefix}-admin-source",
                content=shared_content,
            )
            await create_test_document(
                db=db,
                name=f"{name_prefix}-private-copy",
                content=shared_content,
                current_user_id=user.id,
            )

            try:
                await document_service.grant_document_permission(
                    db=db,
                    document_id=admin_source.id,
                    payload=DocumentPermissionUpsertRequest(
                        user_id=user.id,
                        permission=DocumentPermissionValue.READ,
                    ),
                )
            except DocumentAccessConflictError as exc:
                if "private copy" not in str(exc):
                    raise AssertionError("Share conflict should mention the private copy.")
            else:
                raise AssertionError("Sharing duplicate content should be rejected.")

            try:
                await grant_document_permission_route(
                    document_id=admin_source.id,
                    payload=DocumentPermissionUpsertRequest(
                        user_id=user.id,
                        permission=DocumentPermissionValue.READ,
                    ),
                    db=db,
                    current_admin=admin,
                )
            except HTTPException as exc:
                if exc.status_code != 409 or "private copy" not in str(exc.detail):
                    raise AssertionError("Route should return a 409 private-copy conflict.")
            else:
                raise AssertionError("Permission route should reject duplicate content.")

            permission = await document_service.grant_document_permission(
                db=db,
                document_id=admin_source.id,
                payload=DocumentPermissionUpsertRequest(
                    user_id=other_user.id,
                    permission=DocumentPermissionValue.READ,
                ),
            )
            if permission.user_id != other_user.id:
                raise AssertionError("Non-duplicate shares should still be allowed.")

            user_documents = await list_user_documents_route(
                user_id=user.id,
                page=1,
                page_size=100,
                db=db,
                current_admin=admin,
            )
            user_document_names = {document.name for document in user_documents.items}
            expected_user_document_names = {
                name_prefix,
                f"{name_prefix} (1)",
                f"{name_prefix} (2)",
                f"{name_prefix}-private-copy",
            }
            if not expected_user_document_names.issubset(user_document_names):
                raise AssertionError("Admin user document view should show user-visible docs.")
            if f"{name_prefix}-admin-source" in user_document_names:
                raise AssertionError("Admin user document view should not include hidden docs.")

            admin_documents = await list_user_documents_route(
                user_id=admin.id,
                page=1,
                page_size=100,
                db=db,
                current_admin=admin,
            )
            admin_document_names = {document.name for document in admin_documents.items}
            if f"{name_prefix}-admin-source" not in admin_document_names:
                raise AssertionError("Admin user document view should include all active docs.")
        finally:
            settings.embeddings_enabled = original_embeddings_enabled
            await db.rollback()
            await db.execute(
                delete(Document).where(Document.title.ilike(f"{name_prefix}%"))
            )
            await db.execute(
                delete(User).where(
                    User.email.in_([admin_email, user_email, other_user_email])
                )
            )
            await db.commit()

    print("Document visibility rules OK.")


if __name__ == "__main__":
    try:
        asyncio.run(check_document_visibility_rules())
    except Exception as exc:
        print("Document visibility rules test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
