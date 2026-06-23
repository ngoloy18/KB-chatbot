from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants.constants_documents import DOCUMENT_STATUS_READY
from app.constants.constants_permissions import DOCUMENT_READ_PERMISSIONS
from app.core.config import DocumentCategory
from app.models.models_database import Document, DocumentCategoryModel, DocumentPermission
from app.schemas.schemas_documents import DocumentCreate, DocumentUpdate


class DocumentRepository:
    """SQLAlchemy queries for document persistence."""

    async def list_documents(
        self,
        db: AsyncSession,
        name: str | None = None,
        category: DocumentCategory | None = None,
        page: int = 1,
        page_size: int = 10,
        user_id: UUID | None = None,
        include_all: bool = False,
    ) -> tuple[list[Document], int]:
        """Return matching document ORM rows and their total count."""

        # Build SQL WHERE conditions only for filters the client provided.
        filters = []
        if name is not None:
            filters.append(Document.title.ilike(f"%{name}%"))
        if category is not None:
            filters.append(DocumentCategoryModel.name == category.value)
        if user_id is not None and not include_all:
            # Normal users only see documents where admin granted read-level access.
            filters.append(
                Document.id.in_(
                    select(DocumentPermission.document_id).where(
                        and_(
                            DocumentPermission.user_id == user_id,
                            DocumentPermission.permission.in_(DOCUMENT_READ_PERMISSIONS),
                        )
                    )
                )
            )

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
        return list(result.all()), total or 0

    async def get_document_by_id(
        self,
        db: AsyncSession,
        document_id: UUID,
    ) -> Document | None:
        """Load one document ORM object with its category relationship."""

        query = (
            select(Document)
            .options(selectinload(Document.category))
            .where(Document.id == document_id)
        )
        return await db.scalar(query)

    async def user_has_document_permission(
        self,
        db: AsyncSession,
        document_id: UUID,
        user_id: UUID,
        allowed_permissions: list[str],
    ) -> bool:
        """Return whether a user has one of the allowed permissions."""

        query = select(func.count()).select_from(DocumentPermission).where(
            and_(
                DocumentPermission.document_id == document_id,
                DocumentPermission.user_id == user_id,
                DocumentPermission.permission.in_(allowed_permissions),
            )
        )
        return (await db.scalar(query) or 0) > 0

    async def get_category_by_name(
        self,
        db: AsyncSession,
        category: DocumentCategory,
    ) -> DocumentCategoryModel | None:
        """Load the category row used as a foreign key by documents."""

        query = select(DocumentCategoryModel).where(
            DocumentCategoryModel.name == category.value
        )
        return await db.scalar(query)

    async def create_document(
        self,
        db: AsyncSession,
        payload: DocumentCreate,
        category: DocumentCategoryModel,
    ) -> Document:
        """Build and insert one document row into PostgreSQL."""

        # This object maps to one row in kb.documents.
        document = Document(
            title=payload.name,
            category_id=category.id,
            category=category,
            file_name=payload.file_name,
            file_path=payload.file_path,
            file_type=payload.file_type,
            content=payload.content,
            status=DOCUMENT_STATUS_READY,
        )

        # Add stages the object; commit writes the INSERT to PostgreSQL.
        db.add(document)
        await db.commit()
        return document

    async def update_document(
        self,
        db: AsyncSession,
        document: Document,
        payload: DocumentUpdate,
        category: DocumentCategoryModel | None = None,
    ) -> Document:
        """Apply changed fields to a loaded document row and commit them."""

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
        if category is not None:
            document.category_id = category.id
            document.category = category

        # Commit writes the UPDATE to PostgreSQL.
        await db.commit()
        return document

    async def delete_document(self, db: AsyncSession, document: Document) -> None:
        """Delete one loaded document row from PostgreSQL."""

        await db.delete(document)
        await db.commit()

    async def list_permissions(
        self,
        db: AsyncSession,
        document_id: UUID,
    ) -> list[DocumentPermission]:
        """Return every permission row for one document."""

        query = (
            select(DocumentPermission)
            .where(DocumentPermission.document_id == document_id)
            .order_by(DocumentPermission.created_at.desc())
        )
        rows = await db.scalars(query)
        return list(rows)

    async def get_permission(
        self,
        db: AsyncSession,
        document_id: UUID,
        user_id: UUID,
    ) -> DocumentPermission | None:
        """Return one permission row for one document/user pair."""

        query = select(DocumentPermission).where(
            and_(
                DocumentPermission.document_id == document_id,
                DocumentPermission.user_id == user_id,
            )
        )
        return await db.scalar(query)

    async def upsert_permission(
        self,
        db: AsyncSession,
        document_id: UUID,
        user_id: UUID,
        permission: str,
    ) -> DocumentPermission:
        """Create or update a document permission row."""

        existing_permission = await self.get_permission(db, document_id, user_id)
        if existing_permission is not None:
            existing_permission.permission = permission
            await db.commit()
            await db.refresh(existing_permission)
            return existing_permission

        new_permission = DocumentPermission(
            document_id=document_id,
            user_id=user_id,
            permission=permission,
        )
        db.add(new_permission)
        await db.commit()
        await db.refresh(new_permission)
        return new_permission

    async def delete_permission(
        self,
        db: AsyncSession,
        permission: DocumentPermission,
    ) -> None:
        """Delete one document permission row."""

        await db.delete(permission)
        await db.commit()


document_repository = DocumentRepository()
