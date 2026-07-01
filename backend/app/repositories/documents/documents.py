from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import math
from uuid import UUID

from sqlalchemy import and_, delete, false, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants.documents import DOCUMENT_STATUS_READY
from app.constants.database import SCHEMA_NAME
from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from app.constants.permissions import DOCUMENT_READ_PERMISSIONS
from app.core.config import DocumentCategory
from app.models.database import (
    Document,
    DocumentCategoryModel,
    DocumentChunk,
    DocumentPermission,
    DocumentVersion,
)
from app.schemas.documents.schemas import DocumentCreate, DocumentUpdate


@dataclass(frozen=True)
class DocumentChunkPayload:
    """Chunk data ready to persist, optionally with an embedding."""

    chunk_index: int
    content: str
    token_count: int
    embedding: list[float] | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None


@dataclass(frozen=True)
class DocumentChunkMatch:
    """Retrieved chunk plus document metadata and similarity score."""

    chunk: DocumentChunk
    document: Document
    similarity_score: float


class DocumentRepository:
    """SQLAlchemy queries for document persistence."""

    async def list_documents(
        self,
        db: AsyncSession,
        name: str | None = None,
        category: DocumentCategory | None = None,
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
        user_id: UUID | None = None,
        include_all: bool = False,
    ) -> tuple[list[Document], int]:
        """Return matching document ORM rows and their total count."""

        # Build SQL WHERE conditions only for filters the client provided.
        filters = [Document.is_deleted.is_(False)]
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
        include_deleted: bool = False,
    ) -> Document | None:
        """Load one document ORM object with its category relationship."""

        filters = [Document.id == document_id]
        if not include_deleted:
            filters.append(Document.is_deleted.is_(False))
        query = (
            select(Document)
            .options(selectinload(Document.category))
            .where(*filters)
        )
        return await db.scalar(query)

    async def get_active_document_by_checksum(
        self,
        db: AsyncSession,
        checksum: str,
        exclude_document_id: UUID | None = None,
    ) -> Document | None:
        """Return an active document with the same checksum if one exists."""

        filters = [
            Document.content_checksum == checksum,
            Document.is_deleted.is_(False),
        ]
        if exclude_document_id is not None:
            filters.append(Document.id != exclude_document_id)
        query = select(Document).where(*filters)
        return await db.scalar(query)

    async def list_documents_for_context(
        self,
        db: AsyncSession,
        categories: Sequence[DocumentCategory],
        user_id: UUID | None = None,
        include_all: bool = True,
    ) -> list[Document]:
        """Load full documents for long-context Q&A."""

        category_names = [category.value for category in categories]
        filters = [
            DocumentCategoryModel.name.in_(category_names),
            Document.status == DOCUMENT_STATUS_READY,
            Document.is_deleted.is_(False),
        ]
        if not include_all:
            if user_id is None:
                filters.append(false())
            else:
                filters.append(
                    Document.id.in_(
                        select(DocumentPermission.document_id).where(
                            and_(
                                DocumentPermission.user_id == user_id,
                                DocumentPermission.permission.in_(
                                    DOCUMENT_READ_PERMISSIONS
                                ),
                            )
                        )
                    )
                )

        query = (
            select(Document)
            .join(DocumentCategoryModel)
            .options(selectinload(Document.category))
            .where(*filters)
            .order_by(DocumentCategoryModel.name.asc(), Document.created_at.desc())
        )
        rows = await db.scalars(query)
        return list(rows.all())

    async def search_document_chunks(
        self,
        db: AsyncSession,
        query_text: str,
        category: DocumentCategory | None = None,
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
        user_id: UUID | None = None,
        include_all: bool = False,
    ) -> tuple[list[tuple[DocumentChunk, Document]], int]:
        """Search document chunk content and return matching chunks with documents."""

        filters = [
            DocumentChunk.content.ilike(f"%{query_text}%"),
            Document.status == DOCUMENT_STATUS_READY,
            Document.is_deleted.is_(False),
        ]
        if category is not None:
            filters.append(DocumentCategoryModel.name == category.value)
        if user_id is not None and not include_all:
            # Normal users only search chunks from documents they can read.
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

        total_query = (
            select(func.count())
            .select_from(DocumentChunk)
            .join(Document)
            .join(DocumentCategoryModel)
            .where(*filters)
        )
        total = await db.scalar(total_query)

        search_query = (
            select(DocumentChunk, Document)
            .join(Document)
            .join(DocumentCategoryModel)
            .options(selectinload(Document.category))
            .where(*filters)
            .order_by(Document.updated_at.desc(), DocumentChunk.chunk_index.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = await db.execute(search_query)
        return list(rows.all()), total or 0

    async def search_document_chunks_by_embedding(
        self,
        db: AsyncSession,
        query_embedding: list[float],
        embedding_provider: str,
        embedding_model: str,
        top_k: int,
        min_similarity: float = 0,
        user_id: UUID | None = None,
        include_all: bool = False,
    ) -> list[DocumentChunkMatch]:
        """Return top readable chunks ordered by pgvector cosine similarity."""

        if await _embedding_vector_column_exists(db):
            return await self._search_document_chunks_by_pgvector(
                db=db,
                query_embedding=query_embedding,
                embedding_provider=embedding_provider,
                embedding_model=embedding_model,
                top_k=top_k,
                min_similarity=min_similarity,
                user_id=user_id,
                include_all=include_all,
            )

        filters = [
            DocumentChunk.embedding.is_not(None),
            DocumentChunk.embedding_provider == embedding_provider,
            DocumentChunk.embedding_model == embedding_model,
            Document.status == DOCUMENT_STATUS_READY,
            Document.is_deleted.is_(False),
        ]
        if user_id is not None and not include_all:
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
        elif not include_all:
            filters.append(false())

        candidate_query = (
            select(DocumentChunk, Document)
            .join(Document)
            .join(DocumentCategoryModel)
            .options(selectinload(Document.category))
            .where(*filters)
            .order_by(Document.updated_at.desc(), DocumentChunk.chunk_index.asc())
        )
        rows = await db.execute(candidate_query)
        matches: list[DocumentChunkMatch] = []
        for chunk, document in rows.all():
            if chunk.embedding is None:
                continue
            similarity = _cosine_similarity(
                query_embedding,
                _deserialize_embedding(chunk.embedding),
            )
            if similarity < min_similarity:
                continue
            matches.append(
                DocumentChunkMatch(
                    chunk=chunk,
                    document=document,
                    similarity_score=similarity,
                )
            )
        matches.sort(key=lambda match: match.similarity_score, reverse=True)
        return matches[:top_k]

    async def _search_document_chunks_by_pgvector(
        self,
        db: AsyncSession,
        query_embedding: list[float],
        embedding_provider: str,
        embedding_model: str,
        top_k: int,
        min_similarity: float = 0,
        user_id: UUID | None = None,
        include_all: bool = False,
    ) -> list[DocumentChunkMatch]:
        """Return top readable chunks using PostgreSQL pgvector cosine distance."""

        distance_expression, embedding_cast = await _build_vector_distance_sql(
            db,
            len(query_embedding),
        )
        permission_clause = ""
        params: dict[str, object] = {
            "embedding": _serialize_embedding(query_embedding),
            "embedding_provider": embedding_provider,
            "embedding_model": embedding_model,
            "min_similarity": min_similarity,
            "top_k": top_k,
        }
        if user_id is not None and not include_all:
            permission_clause = f"""
                AND EXISTS (
                    SELECT 1
                    FROM {SCHEMA_NAME}.document_permissions AS p
                    WHERE p.document_id = d.id
                      AND p.user_id = CAST(:user_id AS uuid)
                      AND p.permission IN ('read', 'write', 'owner')
                )
            """
            params["user_id"] = str(user_id)
        elif not include_all:
            permission_clause = "AND FALSE"

        retrieval_query = text(
            f"""
            SELECT
                c.id AS chunk_id,
                1 - ({distance_expression} <=> {embedding_cast}) AS similarity_score
            FROM {SCHEMA_NAME}.document_chunks AS c
            JOIN {SCHEMA_NAME}.documents AS d ON d.id = c.document_id
            WHERE c.embedding_vector IS NOT NULL
              AND c.embedding_provider = :embedding_provider
              AND c.embedding_model = :embedding_model
              AND d.status = 'ready'
              AND d.is_deleted IS FALSE
              {permission_clause}
              AND 1 - ({distance_expression} <=> {embedding_cast}) >= :min_similarity
            ORDER BY {distance_expression} <=> {embedding_cast} ASC
            LIMIT :top_k
            """
        )
        rows = (await db.execute(retrieval_query, params)).all()
        chunk_ids = [row.chunk_id for row in rows]
        if not chunk_ids:
            return []

        score_by_chunk_id = {
            row.chunk_id: float(row.similarity_score)
            for row in rows
        }
        chunk_query = (
            select(DocumentChunk, Document)
            .join(Document)
            .join(DocumentCategoryModel)
            .options(selectinload(Document.category))
            .where(DocumentChunk.id.in_(chunk_ids))
        )
        chunk_rows = (await db.execute(chunk_query)).all()
        match_by_chunk_id = {
            chunk.id: DocumentChunkMatch(
                chunk=chunk,
                document=document,
                similarity_score=score_by_chunk_id[chunk.id],
            )
            for chunk, document in chunk_rows
        }
        return [
            match_by_chunk_id[chunk_id]
            for chunk_id in chunk_ids
            if chunk_id in match_by_chunk_id
        ]

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
            content_checksum=payload.content_checksum,
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
        if payload.content_checksum is not None:
            document.content_checksum = payload.content_checksum
        if category is not None:
            document.category_id = category.id
            document.category = category

        # Commit writes the UPDATE to PostgreSQL.
        await db.commit()
        return document

    async def replace_document_chunks(
        self,
        db: AsyncSession,
        document: Document,
        chunks: list[DocumentChunkPayload],
    ) -> None:
        """Replace every stored chunk for one document."""

        await db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
        )
        db.add_all(
            [
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    embedding=_serialize_embedding(chunk.embedding),
                    embedding_provider=chunk.embedding_provider,
                    embedding_model=chunk.embedding_model,
                    embedding_dimensions=(
                        len(chunk.embedding) if chunk.embedding is not None else None
                    ),
                    embedded_at=(
                        datetime.now(UTC)
                        if chunk.embedding is not None
                        else None
                    ),
                )
                for chunk in chunks
            ]
        )
        await db.commit()
        await _sync_document_chunk_vectors(db, document.id, chunks)

    async def soft_delete_document(self, db: AsyncSession, document: Document) -> Document:
        """Mark one document as deleted without removing its row."""

        document.is_deleted = True
        document.deleted_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(document)
        return document

    async def restore_document(self, db: AsyncSession, document: Document) -> Document:
        """Restore a previously soft-deleted document."""

        document.is_deleted = False
        document.deleted_at = None
        await db.commit()
        await db.refresh(document)
        return document

    async def create_document_version(
        self,
        db: AsyncSession,
        document: Document,
    ) -> DocumentVersion:
        """Create a version snapshot for the current document state."""

        next_version = (
            await db.scalar(
                select(func.max(DocumentVersion.version_number)).where(
                    DocumentVersion.document_id == document.id
                )
            )
            or 0
        ) + 1
        version = DocumentVersion(
            document_id=document.id,
            version_number=next_version,
            title=document.title,
            category_id=document.category_id,
            file_name=document.file_name,
            file_path=document.file_path,
            file_type=document.file_type,
            content_checksum=document.content_checksum,
            content=document.content,
        )
        db.add(version)
        await db.commit()
        await db.refresh(version)
        return version

    async def list_document_versions(
        self,
        db: AsyncSession,
        document_id: UUID,
    ) -> list[DocumentVersion]:
        """Return every version snapshot for one document."""

        query = (
            select(DocumentVersion)
            .options(selectinload(DocumentVersion.category))
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
        )
        rows = await db.scalars(query)
        return list(rows.all())

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


def _serialize_embedding(embedding: list[float] | None) -> str | None:
    """Serialize a vector for storage in PostgreSQL text/pgvector-compatible form."""

    if embedding is None:
        return None
    return json.dumps([float(value) for value in embedding], separators=(",", ":"))


def _deserialize_embedding(embedding: str) -> list[float]:
    """Parse a stored embedding vector."""

    values = json.loads(embedding)
    return [float(value) for value in values]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    """Return cosine similarity for two same-sized vectors."""

    if len(left) != len(right) or not left:
        return 0.0
    dot_product = sum(
        left_value * right_value
        for left_value, right_value in zip(left, right)
    )
    left_norm = math.sqrt(sum(left_value * left_value for left_value in left))
    right_norm = math.sqrt(sum(right_value * right_value for right_value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


async def _embedding_vector_column_exists(db: AsyncSession) -> bool:
    """Return whether this database has the optional pgvector column."""

    exists = await db.scalar(
        text(
            """
            SELECT count(1)
            FROM information_schema.columns
            WHERE table_schema = :schema_name
              AND table_name = 'document_chunks'
              AND column_name = 'embedding_vector'
            """
        ),
        {"schema_name": SCHEMA_NAME},
    )
    return bool(exists)


async def _halfvec_type_exists(db: AsyncSession) -> bool:
    """Return whether this pgvector installation supports halfvec indexes."""

    exists = await db.scalar(
        text(
            """
            SELECT count(1)
            FROM pg_type
            WHERE typname = 'halfvec'
            """
        )
    )
    return bool(exists)


async def _build_vector_distance_sql(
    db: AsyncSession,
    embedding_dimensions: int,
) -> tuple[str, str]:
    """Return the distance expression that can use the best pgvector index."""

    if embedding_dimensions > 2000 and await _halfvec_type_exists(db):
        # pgvector HNSW supports vector up to 2000 dims, while halfvec supports
        # larger Gemini embeddings. Keep this dynamic so models can change.
        return (
            f"c.embedding_vector::halfvec({embedding_dimensions})",
            f"CAST(:embedding AS halfvec({embedding_dimensions}))",
        )
    return "c.embedding_vector", "CAST(:embedding AS vector)"


async def _sync_document_chunk_vectors(
    db: AsyncSession,
    document_id: UUID,
    chunks: list[DocumentChunkPayload],
) -> None:
    """Copy text embeddings into the optional pgvector column when available."""

    if not await _embedding_vector_column_exists(db):
        return
    for chunk in chunks:
        if chunk.embedding is None:
            continue
        await db.execute(
            text(
                f"""
                UPDATE {SCHEMA_NAME}.document_chunks
                SET embedding_vector = CAST(:embedding AS vector)
                WHERE document_id = CAST(:document_id AS uuid)
                  AND chunk_index = :chunk_index
                """
            ),
            {
                "embedding": _serialize_embedding(chunk.embedding),
                "document_id": str(document_id),
                "chunk_index": chunk.chunk_index,
            },
        )
    await db.commit()
