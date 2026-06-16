from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import DocumentCategory
from app.models.models_database import Document, DocumentCategoryModel
from app.schemas.schemas_documents import (
    DocumentCreate,
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdate,
)


class DocumentNotFoundError(ValueError):
    """Raised when a requested document id does not exist."""

    pass


class DocumentCategoryNotFoundError(ValueError):
    """Raised when the configured category rows are missing from the database."""

    pass


class DocumentService:
    """Business logic for managing documents in PostgreSQL."""

    async def list_documents(
        self,
        db: AsyncSession,
        name: str | None = None,
        category: DocumentCategory | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> DocumentListResponse:
        """Return a paginated list of documents after optional filters."""

        # Build SQL WHERE conditions only for filters the client provided.
        filters = []
        if name is not None:
            filters.append(Document.title.ilike(f"%{name}%"))
        if category is not None:
            filters.append(DocumentCategoryModel.name == category.value)

        # Count first so the response can include the total matching rows.
        total_query = (
            select(func.count())
            .select_from(Document)
            .join(DocumentCategoryModel)
            .where(*filters)
        )
        total = await db.scalar(total_query)

        # Load documents plus their category relationship for response serialization.
        documents_query = (
            select(Document)
            .join(DocumentCategoryModel)
            .options(selectinload(Document.category))
            .where(*filters)
            .order_by(Document.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.scalars(documents_query)
        documents = result.all()

        # Convert ORM objects into the API response shape.
        return DocumentListResponse(
            items=[self._to_response(document) for document in documents],
            total=total or 0,
            page=page,
            page_size=page_size,
        )

    async def get_document(
        self,
        db: AsyncSession,
        document_id: UUID,
    ) -> DocumentResponse:
        """Return one document or raise a service-level not-found error."""

        document = await self._get_document_model(db, document_id)
        return self._to_response(document)

    async def create_document(
        self,
        db: AsyncSession,
        payload: DocumentCreate,
    ) -> DocumentResponse:
        """Create a new document in PostgreSQL."""

        # Convert the public enum value into the category row's UUID foreign key.
        category = await self._get_category_model(db, payload.category)

        # This object maps to one row in kb.documents.
        document = Document(
            title=payload.name,
            category_id=category.id,
            category=category,
            file_name=payload.file_name,
            file_path=payload.file_path,
            file_type=payload.file_type,
            content=payload.content,
            status="ready",
        )

        # Add stages the object; commit writes the INSERT to PostgreSQL.
        db.add(document)
        await db.commit()
        return self._to_response(document)

    async def update_document(
        self,
        db: AsyncSession,
        document_id: UUID,
        payload: DocumentUpdate,
    ) -> DocumentResponse:
        """Update only the fields supplied in the request body."""

        # Reuse the helper so missing documents get the same not-found behavior.
        document = await self._get_document_model(db, document_id)

        # Each field is optional for update, so only provided values are changed.
        if payload.name is not None:
            document.title = payload.name
        if payload.content is not None:
            document.content = payload.content
        if payload.file_name is not None:
            document.file_name = payload.file_name
        if payload.file_path is not None:
            document.file_path = payload.file_path
        if payload.file_type is not None:
            document.file_type = payload.file_type
        if payload.category is not None:
            # Category updates need a lookup because documents store category_id.
            category = await self._get_category_model(db, payload.category)
            document.category_id = category.id
            document.category = category

        # Commit writes the UPDATE to PostgreSQL.
        await db.commit()
        return self._to_response(document)

    async def delete_document(self, db: AsyncSession, document_id: UUID) -> None:
        """Delete one document or raise if the id is unknown."""

        # Loading first lets us return 404 instead of silently doing nothing.
        document = await self._get_document_model(db, document_id)
        await db.delete(document)
        await db.commit()

    async def _get_document_model(
        self,
        db: AsyncSession,
        document_id: UUID,
    ) -> Document:
        """Load one document ORM object with its category relationship."""

        query = (
            select(Document)
            .options(selectinload(Document.category))
            .where(Document.id == document_id)
        )
        document = await db.scalar(query)
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} was not found.")
        return document

    async def _get_category_model(
        self,
        db: AsyncSession,
        category: DocumentCategory,
    ) -> DocumentCategoryModel:
        """Load the category row used as a foreign key by documents."""

        query = select(DocumentCategoryModel).where(
            DocumentCategoryModel.name == category.value
        )
        category_model = await db.scalar(query)
        if category_model is None:
            raise DocumentCategoryNotFoundError(
                f"Document category {category.value} was not found in the database."
            )
        return category_model

    def _to_response(self, document: Document) -> DocumentResponse:
        """Convert a SQLAlchemy Document model into the public API schema."""

        return DocumentResponse(
            id=document.id,
            name=document.title,
            category=DocumentCategory(document.category.name),
            file_name=document.file_name,
            file_path=document.file_path,
            file_type=document.file_type,
            content=document.content,
            created_at=document.created_at,
        )


document_service = DocumentService()
