from datetime import UTC, datetime

from app.core.config import DocumentCategory
from app.schemas.schemas_documents import (
    DocumentCreate,
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdate,
)


class DocumentNotFoundError(ValueError):
    """Raised when a requested document id does not exist in the service."""

    pass


class DocumentService:
    """Business logic for managing documents.

    This service currently stores data in memory, so documents are lost when the
    API process restarts. The class shape still keeps storage logic separate
    from the HTTP routes, which makes it easier to replace with a database later.
    """

    def __init__(self) -> None:
        # Key documents by id so lookups, updates, and deletes are direct.
        self._documents: dict[int, DocumentResponse] = {}

        # Simple auto-incrementing id counter for the in-memory store.
        self._next_id = 1

    async def list_documents(
        self,
        name: str | None = None,
        category: DocumentCategory | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> DocumentListResponse:
        """Return a paginated list of documents after optional filters."""

        documents = list(self._documents.values())

        # Apply category filtering first because it is an exact enum match.
        if category is not None:
            documents = [
                document for document in documents if document.category == category
            ]

        # Name search is case-insensitive and matches any part of the title.
        if name is not None:
            documents = [
                document
                for document in documents
                if name.lower() in document.name.lower()
            ]

        # Pagination is done after filtering so total describes the filtered set.
        total = len(documents)
        start = (page - 1) * page_size
        end = start + page_size

        return DocumentListResponse(
            items=documents[start:end],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_document(self, document_id: int) -> DocumentResponse:
        """Return one document or raise a service-level not-found error."""

        document = self._documents.get(document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} was not found.")
        return document

    async def create_document(self, payload: DocumentCreate) -> DocumentResponse:
        """Create a new document with a generated id and UTC timestamp."""

        document = DocumentResponse(
            id=self._next_id,
            name=payload.name,
            category=payload.category,
            content=payload.content,
            created_at=datetime.now(UTC),
        )
        self._documents[document.id] = document
        self._next_id += 1
        return document

    async def update_document(
        self, document_id: int, payload: DocumentUpdate
    ) -> DocumentResponse:
        """Update only the fields supplied in the request body."""

        document = await self.get_document(document_id)

        # exclude_unset keeps missing fields unchanged; exclude_none also ignores
        # fields explicitly sent as null so required document data is not erased.
        update_data = payload.model_dump(exclude_unset=True, exclude_none=True)

        # Pydantic creates a copied model so the existing response schema remains
        # the single source of truth for stored document shape.
        updated_document = document.model_copy(update=update_data)
        self._documents[document_id] = updated_document
        return updated_document

    async def delete_document(self, document_id: int) -> None:
        """Delete one document or raise if the id is unknown."""

        if document_id not in self._documents:
            raise DocumentNotFoundError(f"Document {document_id} was not found.")
        del self._documents[document_id]


# Shared service instance used by the routes module.
document_service = DocumentService()
