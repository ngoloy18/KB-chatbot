from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.constants_permissions import (
    DOCUMENT_DELETE_PERMISSIONS,
    DOCUMENT_READ_PERMISSIONS,
    DOCUMENT_WRITE_PERMISSIONS,
)
from app.core.config import DocumentCategory
from app.models.models_database import Document
from app.repositories.repositories_documents import document_repository
from app.repositories.repositories_users import user_repository
from app.schemas.schemas_documents import (
    DocumentCreate,
    DocumentListResponse,
    DocumentPermissionResponse,
    DocumentPermissionUpsertRequest,
    DocumentResponse,
    DocumentUpdate,
    document_to_response,
)
from app.services.exceptions_documents import (
    DocumentAccessDeniedError,
    DocumentCategoryNotFoundError,
    DocumentNotFoundError,
    DocumentPermissionNotFoundError,
)
from app.services.exceptions_users import UserNotFoundError


class DocumentService:
    """Business logic for managing documents."""

    async def list_documents(
        self,
        db: AsyncSession,
        name: str | None = None,
        category: DocumentCategory | None = None,
        page: int = 1,
        page_size: int = 10,
        current_user_id: UUID | None = None,
        is_admin: bool = False,
    ) -> DocumentListResponse:
        """Return a paginated list of documents after optional filters."""

        documents, total = await document_repository.list_documents(
            db=db,
            name=name,
            category=category,
            page=page,
            page_size=page_size,
            user_id=current_user_id,
            include_all=is_admin,
        )

        # Convert repository results into the API response shape.
        return DocumentListResponse(
            items=[document_to_response(document) for document in documents],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_document(
        self,
        db: AsyncSession,
        document_id: UUID,
        current_user_id: UUID | None = None,
        is_admin: bool = False,
    ) -> DocumentResponse:
        """Return one document or raise a service-level not-found error."""

        document = await self._get_document_or_raise(db, document_id)
        if not is_admin:
            if current_user_id is None:
                raise DocumentAccessDeniedError("Login is required to read documents.")
            user_can_read = await document_repository.user_has_document_permission(
                db,
                document_id,
                current_user_id,
                DOCUMENT_READ_PERMISSIONS,
            )
            if not user_can_read:
                raise DocumentAccessDeniedError("You do not have access to this document.")
        return document_to_response(document)

    async def create_document(
        self,
        db: AsyncSession,
        payload: DocumentCreate,
    ) -> DocumentResponse:
        """Create a new document."""

        # Convert the public enum value into the category row's UUID foreign key.
        category = await document_repository.get_category_by_name(db, payload.category)
        if category is None:
            raise DocumentCategoryNotFoundError(
                f"Document category {payload.category.value} was not found in the database."
            )

        document = await document_repository.create_document(
            db=db,
            payload=payload,
            category=category,
        )
        return document_to_response(document)

    async def update_document(
        self,
        db: AsyncSession,
        document_id: UUID,
        payload: DocumentUpdate,
        current_user_id: UUID | None = None,
        is_admin: bool = False,
    ) -> DocumentResponse:
        """Update only the fields supplied in the request body."""

        # Reuse the helper so missing documents get the same not-found behavior.
        document = await self._get_document_or_raise(db, document_id)
        if not is_admin:
            if current_user_id is None:
                raise DocumentAccessDeniedError("Login is required to update documents.")
            user_can_write = await document_repository.user_has_document_permission(
                db,
                document_id,
                current_user_id,
                DOCUMENT_WRITE_PERMISSIONS,
            )
            if not user_can_write:
                raise DocumentAccessDeniedError("Write permission is required.")

        category = None
        if payload.category is not None:
            # Category updates need a lookup because documents store category_id.
            category = await document_repository.get_category_by_name(
                db,
                payload.category,
            )
            if category is None:
                raise DocumentCategoryNotFoundError(
                    f"Document category {payload.category.value} was not found in the database."
                )

        document = await document_repository.update_document(
            db=db,
            document=document,
            payload=payload,
            category=category,
        )
        return document_to_response(document)

    async def delete_document(
        self,
        db: AsyncSession,
        document_id: UUID,
        current_user_id: UUID | None = None,
        is_admin: bool = False,
    ) -> None:
        """Delete one document or raise if the id is unknown."""

        # Loading first lets us return 404 instead of silently doing nothing.
        document = await self._get_document_or_raise(db, document_id)
        if not is_admin:
            if current_user_id is None:
                raise DocumentAccessDeniedError("Login is required to delete documents.")
            user_can_delete = await document_repository.user_has_document_permission(
                db,
                document_id,
                current_user_id,
                DOCUMENT_DELETE_PERMISSIONS,
            )
            if not user_can_delete:
                raise DocumentAccessDeniedError("Owner permission is required.")
        await document_repository.delete_document(db, document)

    async def list_document_permissions(
        self,
        db: AsyncSession,
        document_id: UUID,
    ) -> list[DocumentPermissionResponse]:
        """Return every user permission for one document."""

        await self._get_document_or_raise(db, document_id)
        permissions = await document_repository.list_permissions(db, document_id)
        return [
            DocumentPermissionResponse.model_validate(permission)
            for permission in permissions
        ]

    async def grant_document_permission(
        self,
        db: AsyncSession,
        document_id: UUID,
        payload: DocumentPermissionUpsertRequest,
    ) -> DocumentPermissionResponse:
        """Grant or change one user's permission for a document."""

        await self._get_document_or_raise(db, document_id)
        user = await user_repository.get_by_id(db, payload.user_id)
        if user is None:
            raise UserNotFoundError("User not found.")

        permission = await document_repository.upsert_permission(
            db=db,
            document_id=document_id,
            user_id=payload.user_id,
            permission=payload.permission.value,
        )
        return DocumentPermissionResponse.model_validate(permission)

    async def revoke_document_permission(
        self,
        db: AsyncSession,
        document_id: UUID,
        user_id: UUID,
    ) -> None:
        """Remove one user's permission for a document."""

        await self._get_document_or_raise(db, document_id)
        permission = await document_repository.get_permission(db, document_id, user_id)
        if permission is None:
            raise DocumentPermissionNotFoundError("Document permission not found.")
        await document_repository.delete_permission(db, permission)

    async def _get_document_or_raise(
        self,
        db: AsyncSession,
        document_id: UUID,
    ) -> Document:
        """Load one document or raise a service-level not-found error."""

        document = await document_repository.get_document_by_id(db, document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} was not found.")
        return document
