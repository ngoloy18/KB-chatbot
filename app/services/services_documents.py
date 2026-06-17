from uuid import UUID
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import DocumentCategory
from app.mappers.mappers_documents import document_to_response
from app.repositories.repositories_documents import document_repository
from app.schemas.schemas_documents import (
    DocumentCreate,
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdate,
)
from app.services.exceptions_documents import (
    DocumentCategoryNotFoundError,
    DocumentNotFoundError,
)


class DocumentService:
    """Business logic for managing documents."""

    async def list_documents(
        self,
        db: AsyncSession,
        name: str | None = None,
        category: DocumentCategory | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> DocumentListResponse:
        """Return a paginated list of documents after optional filters."""

        documents, total = await document_repository.list_documents(
            db=db,
            name=name,
            category=category,
            page=page,
            page_size=page_size,
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
    ) -> DocumentResponse:
        """Return one document or raise a service-level not-found error."""

        document = await self._get_document_or_raise(db, document_id)
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
    ) -> DocumentResponse:
        """Update only the fields supplied in the request body."""

        # Reuse the helper so missing documents get the same not-found behavior.
        document = await self._get_document_or_raise(db, document_id)

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

    async def delete_document(self, db: AsyncSession, document_id: UUID) -> None:
        """Delete one document or raise if the id is unknown."""

        # Loading first lets us return 404 instead of silently doing nothing.
        document = await self._get_document_or_raise(db, document_id)
        await document_repository.delete_document(db, document)

    async def _get_document_or_raise(
        self,
        db: AsyncSession,
        document_id: UUID,
    ) -> Any:
        """Load one document or raise a service-level not-found error."""

        document = await document_repository.get_document_by_id(db, document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} was not found.")
        return document
