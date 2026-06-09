# This file defines the DocumentService class, which provides methods for managing documents in memory.
# It also defines a custom exception DocumentNotFoundError for handling cases where a document is not
from datetime import UTC, datetime
from app.core.config import DocumentCategory
from app.schemas.schemas_documents import (
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
)


# This file defines the DocumentService class, which provides methods for managing documents in memory.
class DocumentNotFoundError(ValueError):
    pass


# The DocumentService class provides methods for listing, retrieving, creating, updating, and deleting documents.
class DocumentService:
    # The service uses an in-memory dictionary to store documents, with auto-incrementing integer IDs.
    def __init__(self) -> None:
        self._documents: dict[int, DocumentResponse] = {}
        self._next_id = 1

    # List documents, optionally filtered by category
    async def list_documents(
        self, category: DocumentCategory | None = None
    ) -> list[DocumentResponse]:
        documents = list(self._documents.values())
        if category is None:
            return documents
        return [document for document in documents if document.category == category]

    # Get one document by id, or raise DocumentNotFoundError if it doesn't exist
    async def get_document(self, document_id: int) -> DocumentResponse:
        document = self._documents.get(document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} was not found.")
        return document

    # Create a document from a DocumentCreate payload, generating its id and creation timestamp
    async def create_document(self, payload: DocumentCreate) -> DocumentResponse:
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

    # Update a document by id, with partial update support (only fields provided in the request body will be updated)
    async def update_document(
        self, document_id: int, payload: DocumentUpdate
    ) -> DocumentResponse:
        document = await self.get_document(document_id)
        update_data = payload.model_dump(exclude_unset=True, exclude_none=True)
        updated_document = document.model_copy(update=update_data)
        self._documents[document_id] = updated_document
        return updated_document

    # Delete a document by id, or raise DocumentNotFoundError if it doesn't exist
    async def delete_document(self, document_id: int) -> None:
        if document_id not in self._documents:
            raise DocumentNotFoundError(f"Document {document_id} was not found.")
        del self._documents[document_id]


document_service = DocumentService()
