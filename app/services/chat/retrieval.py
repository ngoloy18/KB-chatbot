from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.documents.documents import (
    DocumentChunkMatch,
    document_repository,
)
from app.services.ai import create_embedding_provider


@dataclass(frozen=True)
class RetrievedSource:
    """Source chunk metadata used for citations and message_sources rows."""

    document_id: UUID
    chunk_id: UUID
    name: str
    category: str
    similarity_score: float | None = None


@dataclass(frozen=True)
class RetrievedContext:
    """Chunk-level context retrieved for one chat question."""

    content: str
    sources: list[RetrievedSource]

    @property
    def source_names(self) -> list[str]:
        """Return unique source document names in retrieval order."""

        names: list[str] = []
        for source in self.sources:
            if source.name not in names:
                names.append(source.name)
        return names


async def retrieve_chat_context(
    db: AsyncSession,
    question: str,
    user_id: UUID,
    include_all: bool,
) -> RetrievedContext:
    """Retrieve top readable chunks for a chat question."""

    if settings.embeddings_enabled:
        return await _retrieve_semantic_context(
            db=db,
            question=question,
            user_id=user_id,
            include_all=include_all,
        )
    return await _retrieve_keyword_context(
        db=db,
        question=question,
        user_id=user_id,
        include_all=include_all,
    )


async def _retrieve_semantic_context(
    db: AsyncSession,
    question: str,
    user_id: UUID,
    include_all: bool,
) -> RetrievedContext:
    """Retrieve chunks by pgvector cosine similarity."""

    embedding_provider = create_embedding_provider()
    query_embedding = await embedding_provider.embed_query(question)
    matches = await document_repository.search_document_chunks_by_embedding(
        db=db,
        query_embedding=query_embedding,
        embedding_provider=embedding_provider.provider_name,
        embedding_model=embedding_provider.model_name,
        top_k=settings.rag_top_k,
        min_similarity=settings.rag_min_similarity,
        user_id=user_id,
        include_all=include_all,
    )
    return _build_context(matches)


async def _retrieve_keyword_context(
    db: AsyncSession,
    question: str,
    user_id: UUID,
    include_all: bool,
) -> RetrievedContext:
    """Fallback RAG retrieval when embeddings are disabled."""

    rows, _ = await document_repository.search_document_chunks(
        db=db,
        query_text=question.strip(),
        page=1,
        page_size=settings.rag_top_k,
        user_id=user_id,
        include_all=include_all,
    )
    matches = [
        DocumentChunkMatch(
            chunk=chunk,
            document=document,
            similarity_score=1.0,
        )
        for chunk, document in rows
    ]
    return _build_context(matches)


def _build_context(matches: list[DocumentChunkMatch]) -> RetrievedContext:
    """Format retrieved chunks and enforce the configured token budget."""

    blocks: list[str] = []
    sources: list[RetrievedSource] = []
    used_tokens = 0
    token_budget = max(settings.rag_max_context_tokens, 0)

    for match in matches:
        chunk_tokens = match.chunk.token_count or len(match.chunk.content.split())
        if token_budget and blocks and used_tokens + chunk_tokens > token_budget:
            continue

        used_tokens += chunk_tokens
        source_name = match.document.title
        category_name = match.document.category.name
        blocks.append(
            (
                f"=== {source_name} ({category_name}) "
                f"| chunk {match.chunk.chunk_index} "
                f"| similarity {match.similarity_score:.3f} ===\n"
                f"{match.chunk.content.strip()}"
            )
        )
        sources.append(
            RetrievedSource(
                document_id=match.document.id,
                chunk_id=match.chunk.id,
                name=source_name,
                category=category_name,
                similarity_score=match.similarity_score,
            )
        )

    return RetrievedContext(content="\n\n".join(blocks), sources=sources)
