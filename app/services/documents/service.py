import hashlib
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.permissions import (
    DOCUMENT_DELETE_PERMISSIONS,
    DOCUMENT_READ_PERMISSIONS,
    DOCUMENT_WRITE_PERMISSIONS,
)
from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from app.core.config import DocumentCategory
from app.models.database import Document
from app.repositories.documents.documents import document_repository
from app.repositories.users.users import user_repository
from app.schemas.documents.schemas import (
    DocumentCreate,
    DocumentChunkSearchResponse,
    DocumentChunkSearchResult,
    DocumentListResponse,
    DocumentPermissionResponse,
    DocumentPermissionUpsertRequest,
    DocumentResponse,
    DocumentUpdate,
    DocumentVersionListResponse,
    DocumentVersionResponse,
    document_to_response,
)
from app.services.documents.exceptions import (
    DocumentAccessDeniedError,
    DocumentCategoryNotFoundError,
    DocumentDuplicateError,
    DocumentNotFoundError,
    DocumentPermissionNotFoundError,
)
from app.services.documents.chunking import document_chunking_service
from app.services.users.exceptions import UserNotFoundError


class DocumentService:
    """Business logic for managing documents."""

    async def list_documents(
        self,
        db: AsyncSession,
        name: str | None = None,
        category: DocumentCategory | None = None,
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
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

    async def search_document_chunks(
        self,
        db: AsyncSession,
        query: str,
        category: DocumentCategory | None = None,
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
        current_user_id: UUID | None = None,
        is_admin: bool = False,
    ) -> DocumentChunkSearchResponse:
        """Search document chunks visible to the current user."""

        rows, total = await document_repository.search_document_chunks(
            db=db,
            query_text=query,
            category=category,
            page=page,
            page_size=page_size,
            user_id=current_user_id,
            include_all=is_admin,
        )
        return DocumentChunkSearchResponse(
            items=[
                DocumentChunkSearchResult(
                    document_id=document.id,
                    document_name=document.title,
                    category=DocumentCategory(document.category.name),
                    chunk_id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    token_count=chunk.token_count,
                )
                for chunk, document in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
            query=query,
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

        checksum = payload.content_checksum or self._calculate_content_checksum(
            payload.content
        )
        await self._raise_if_duplicate_checksum(db, checksum)
        payload = payload.model_copy(update={"content_checksum": checksum})

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
        await self._replace_document_chunks(db, document, payload.content)
        await document_repository.create_document_version(db, document)
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

        if payload.content is not None:
            checksum = payload.content_checksum or self._calculate_content_checksum(
                payload.content
            )
            await self._raise_if_duplicate_checksum(
                db,
                checksum,
                exclude_document_id=document_id,
            )
            payload = payload.model_copy(update={"content_checksum": checksum})

        document = await document_repository.update_document(
            db=db,
            document=document,
            payload=payload,
            category=category,
        )
        if payload.content is not None:
            await self._replace_document_chunks(db, document, payload.content)
        await document_repository.create_document_version(db, document)
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
        await document_repository.soft_delete_document(db, document)

    async def restore_document(
        self,
        db: AsyncSession,
        document_id: UUID,
        current_user_id: UUID | None = None,
        is_admin: bool = False,
    ) -> DocumentResponse:
        """Restore one soft-deleted document."""

        document = await self._get_document_or_raise(
            db,
            document_id,
            include_deleted=True,
        )
        if not is_admin:
            if current_user_id is None:
                raise DocumentAccessDeniedError("Login is required to restore documents.")
            user_can_restore = await document_repository.user_has_document_permission(
                db,
                document_id,
                current_user_id,
                DOCUMENT_DELETE_PERMISSIONS,
            )
            if not user_can_restore:
                raise DocumentAccessDeniedError("Owner permission is required.")
        if document.content_checksum is not None:
            await self._raise_if_duplicate_checksum(
                db,
                document.content_checksum,
                exclude_document_id=document.id,
            )
        restored = await document_repository.restore_document(db, document)
        return document_to_response(restored)

    async def list_document_versions(
        self,
        db: AsyncSession,
        document_id: UUID,
        current_user_id: UUID | None = None,
        is_admin: bool = False,
    ) -> DocumentVersionListResponse:
        """Return version history for one document."""

        document = await self._get_document_or_raise(
            db,
            document_id,
            include_deleted=True,
        )
        if not is_admin:
            if current_user_id is None:
                raise DocumentAccessDeniedError("Login is required to read versions.")
            user_can_read = await document_repository.user_has_document_permission(
                db,
                document_id,
                current_user_id,
                DOCUMENT_READ_PERMISSIONS,
            )
            if not user_can_read:
                raise DocumentAccessDeniedError("You do not have access to this document.")

        versions = await document_repository.list_document_versions(db, document.id)
        return DocumentVersionListResponse(
            items=[
                DocumentVersionResponse(
                    id=version.id,
                    document_id=version.document_id,
                    version_number=version.version_number,
                    name=version.title,
                    category=DocumentCategory(version.category.name),
                    file_name=version.file_name,
                    file_path=version.file_path,
                    file_type=version.file_type,
                    content_checksum=version.content_checksum,
                    content=version.content,
                    created_at=version.created_at,
                )
                for version in versions
            ],
            total=len(versions),
        )

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
        include_deleted: bool = False,
    ) -> Document:
        """Load one document or raise a service-level not-found error."""

        document = await document_repository.get_document_by_id(
            db,
            document_id,
            include_deleted=include_deleted,
        )
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} was not found.")
        return document

    async def _raise_if_duplicate_checksum(
        self,
        db: AsyncSession,
        checksum: str,
        exclude_document_id: UUID | None = None,
    ) -> None:
        """Raise when another active document already has this checksum."""

        duplicate = await document_repository.get_active_document_by_checksum(
            db,
            checksum,
            exclude_document_id=exclude_document_id,
        )
        if duplicate is not None:
            raise DocumentDuplicateError(
                f"An active document with the same checksum already exists: {duplicate.id}."
            )

    @staticmethod
    def _calculate_content_checksum(content: str) -> str:
        """Return a stable SHA-256 checksum for document content."""

        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def _replace_document_chunks(
        self,
        db: AsyncSession,
        document: Document,
        content: str,
    ) -> None:
        """Split document text and replace rows in kb.document_chunks."""

        chunks = document_chunking_service.split_text(content)
        await document_repository.replace_document_chunks(
            db=db,
            document=document,
            chunks=[
                (chunk.chunk_index, chunk.content, chunk.token_count)
                for chunk in chunks
            ],
        )
