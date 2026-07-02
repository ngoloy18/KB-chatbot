from dataclasses import dataclass
import logging
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.documents.documents import (
    DocumentChunkMatch,
    document_repository,
)
from app.services.ai import create_embedding_provider


logger = logging.getLogger(__name__)

KEYWORD_STOP_WORDS = {
    "about",
    "after",
    "again",
    "answer",
    "before",
    "current",
    "document",
    "documents",
    "from",
    "have",
    "how",
    "into",
    "that",
    "their",
    "there",
    "this",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
    "your",
}


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
    keyword_matches = await _search_keyword_matches(
        db=db,
        question=question,
        user_id=user_id,
        include_all=include_all,
    )
    matches = _merge_matches(matches, keyword_matches)
    matches = await _expand_neighbor_matches(db, matches)
    _log_retrieved_matches("semantic", matches)
    return _build_context(matches)


async def _retrieve_keyword_context(
    db: AsyncSession,
    question: str,
    user_id: UUID,
    include_all: bool,
) -> RetrievedContext:
    """Fallback RAG retrieval when embeddings are disabled."""

    matches = await _search_keyword_matches(
        db=db,
        question=question,
        user_id=user_id,
        include_all=include_all,
    )
    matches = await _expand_neighbor_matches(db, matches)
    _log_retrieved_matches("keyword", matches)
    return _build_context(matches)


async def _search_keyword_matches(
    db: AsyncSession,
    question: str,
    user_id: UUID,
    include_all: bool,
) -> list[DocumentChunkMatch]:
    """Supplement semantic retrieval with simple readable keyword matches."""

    matches: list[DocumentChunkMatch] = []
    seen_chunk_ids: set[UUID] = set()
    for query_text in _build_keyword_queries(question):
        rows, _ = await document_repository.search_document_chunks(
            db=db,
            query_text=query_text,
            page=1,
            page_size=settings.rag_top_k,
            user_id=user_id,
            include_all=include_all,
        )
        for chunk, document in rows:
            if chunk.id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk.id)
            matches.append(
                DocumentChunkMatch(
                    chunk=chunk,
                    document=document,
                    similarity_score=1.0,
                )
            )
            if len(matches) >= settings.rag_top_k:
                return matches
    return matches


def _build_keyword_queries(question: str) -> list[str]:
    """Return a few keyword queries from the user question."""

    clean_question = question.strip()
    queries: list[str] = []
    if clean_question:
        queries.append(clean_question)

    for word in re.findall(r"[a-zA-Z0-9_/-]{4,}", clean_question.lower()):
        if word in KEYWORD_STOP_WORDS or word in queries:
            continue
        queries.append(word)
        if len(queries) >= 4:
            break
    return queries


def _merge_matches(
    semantic_matches: list[DocumentChunkMatch],
    keyword_matches: list[DocumentChunkMatch],
) -> list[DocumentChunkMatch]:
    """Keep semantic rank first, then add non-duplicate keyword matches."""

    merged_matches: list[DocumentChunkMatch] = []
    seen_chunk_ids: set[UUID] = set()
    for match in [*semantic_matches, *keyword_matches]:
        if match.chunk.id in seen_chunk_ids:
            continue
        seen_chunk_ids.add(match.chunk.id)
        merged_matches.append(match)
    return merged_matches


async def _expand_neighbor_matches(
    db: AsyncSession,
    matches: list[DocumentChunkMatch],
) -> list[DocumentChunkMatch]:
    """Include nearby chunks when configured."""

    return await document_repository.expand_chunk_neighbors(
        db=db,
        matches=matches,
        neighbor_window=max(settings.rag_neighbor_window, 0),
    )


def _build_context(matches: list[DocumentChunkMatch]) -> RetrievedContext:
    """Format retrieved chunks and enforce the configured token budget."""

    blocks: list[str] = []
    sources: list[RetrievedSource] = []
    used_tokens = 0
    token_budget = max(settings.rag_max_context_tokens, 0)

    for match in matches:
        chunk_tokens = match.chunk.token_count or len(match.chunk.content.split())
        if token_budget and blocks and used_tokens + chunk_tokens > token_budget:
            if settings.rag_debug_enabled:
                logger.info(
                    "event=rag.chunk_skipped_budget document_id=%s chunk_id=%s "
                    "chunk_index=%s token_count=%s used_tokens=%s token_budget=%s",
                    match.document.id,
                    match.chunk.id,
                    match.chunk.chunk_index,
                    chunk_tokens,
                    used_tokens,
                    token_budget,
                )
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


def _log_retrieved_matches(
    retrieval_mode: str,
    matches: list[DocumentChunkMatch],
) -> None:
    """Log retrieved chunks for RAG debugging when enabled."""

    if not settings.rag_debug_enabled:
        return
    if not matches:
        logger.info("event=rag.no_matches mode=%s", retrieval_mode)
        return

    for rank, match in enumerate(matches, start=1):
        preview = " ".join(match.chunk.content.split())[:240]
        logger.info(
            "event=rag.retrieved_chunk mode=%s rank=%s document_id=%s "
            "chunk_id=%s chunk_index=%s similarity=%.4f token_count=%s preview=%r",
            retrieval_mode,
            rank,
            match.document.id,
            match.chunk.id,
            match.chunk.chunk_index,
            match.similarity_score,
            match.chunk.token_count,
            preview,
        )
