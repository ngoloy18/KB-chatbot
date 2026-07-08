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
    "being",
    "before",
    "does",
    "doing",
    "done",
    "current",
    "document",
    "documents",
    "from",
    "have",
    "how",
    "into",
    "must",
    "need",
    "needs",
    "should",
    "that",
    "their",
    "there",
    "this",
    "instead",
    "use",
    "used",
    "uses",
    "using",
    "what",
    "when",
    "where",
    "which",
    "will",
    "with",
    "would",
    "your",
}

MAX_KEYWORD_QUERIES = 8
RETRIEVAL_CANDIDATE_MULTIPLIER = 3
CHUNK_LEXICAL_WEIGHT = 0.35
METADATA_LEXICAL_WEIGHT = 0.15
EXACT_PHRASE_WEIGHT = 0.1
AUTHORITY_SOURCE_WEIGHT = 0.25
CONTENT_AUTHORITY_WEIGHT = 0.08
MAX_RANKING_CONTENT_WORDS = 220

AUTHORITY_QUERY_TERMS = {
    "best",
    "must",
    "need",
    "needed",
    "recommend",
    "recommended",
    "require",
    "required",
    "requirement",
    "requirements",
    "rule",
    "rules",
    "should",
    "standard",
    "standards",
    "use",
    "when",
    "which",
}
AUTHORITY_SOURCE_TERMS = {
    "convention",
    "conventions",
    "guideline",
    "guidelines",
    "policy",
    "policies",
    "requirement",
    "requirements",
    "rule",
    "rules",
    "standard",
    "standards",
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


@dataclass(frozen=True)
class KeywordQuery:
    """Keyword query text plus its relative lexical relevance."""

    text: str
    score: float


@dataclass(frozen=True)
class RankedMatch:
    """Candidate match plus generic ranking signals."""

    score: float
    index: int
    match: DocumentChunkMatch
    chunk_overlap: float
    phrase_overlap: float
    metadata_overlap: float
    authority_score: float


async def retrieve_chat_context(
    db: AsyncSession,
    question: str,
    user_id: UUID,
    include_all: bool,
) -> RetrievedContext:
    """Retrieve top readable chunks for a chat question."""

    if settings.rag_top_k <= 0:
        return RetrievedContext(content="", sources=[])
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
    candidate_limit = _retrieval_candidate_limit()
    matches = await document_repository.search_document_chunks_by_embedding(
        db=db,
        query_embedding=query_embedding,
        embedding_provider=embedding_provider.provider_name,
        embedding_model=embedding_provider.model_name,
        top_k=candidate_limit,
        min_similarity=settings.rag_min_similarity,
        user_id=user_id,
        include_all=include_all,
    )
    keyword_matches = await _search_keyword_matches(
        db=db,
        question=question,
        user_id=user_id,
        include_all=include_all,
        max_matches=candidate_limit,
    )
    matches = _merge_and_rank_matches(
        semantic_matches=matches,
        keyword_matches=keyword_matches,
        question=question,
        max_matches=settings.rag_top_k,
    )
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

    candidate_limit = _retrieval_candidate_limit()
    matches = await _search_keyword_matches(
        db=db,
        question=question,
        user_id=user_id,
        include_all=include_all,
        max_matches=candidate_limit,
    )
    matches = _merge_and_rank_matches(
        semantic_matches=[],
        keyword_matches=matches,
        question=question,
        max_matches=settings.rag_top_k,
    )
    matches = await _expand_neighbor_matches(db, matches)
    _log_retrieved_matches("keyword", matches)
    return _build_context(matches)


async def _search_keyword_matches(
    db: AsyncSession,
    question: str,
    user_id: UUID,
    include_all: bool,
    max_matches: int,
) -> list[DocumentChunkMatch]:
    """Supplement semantic retrieval with simple readable keyword matches."""

    matches: list[DocumentChunkMatch] = []
    seen_chunk_ids: set[UUID] = set()
    if max_matches <= 0:
        return matches

    for keyword_query in _build_keyword_queries(question):
        rows, _ = await document_repository.search_document_chunks(
            db=db,
            query_text=keyword_query.text,
            page=1,
            page_size=max_matches,
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
                    similarity_score=keyword_query.score,
                )
            )
            if len(matches) >= max_matches:
                return matches
    return matches


def _build_keyword_queries(question: str) -> list[KeywordQuery]:
    """Return a few keyword queries from the user question."""

    clean_question = question.strip()
    queries: list[KeywordQuery] = []
    seen_queries: set[str] = set()

    def add_query(text: str, score: float) -> None:
        normalized_text = " ".join(text.lower().split())
        if not normalized_text or normalized_text in seen_queries:
            return
        seen_queries.add(normalized_text)
        queries.append(KeywordQuery(text=normalized_text, score=score))

    if clean_question:
        add_query(clean_question, 0.9)

    keywords = _important_keywords(clean_question)
    if len(keywords) >= 2:
        add_query(" ".join(keywords[:4]), 0.86)
        for index in range(len(keywords) - 1):
            add_query(f"{keywords[index]} {keywords[index + 1]}", 0.82)
    for word in keywords:
        add_query(word, 0.68)

    return queries[:MAX_KEYWORD_QUERIES]


def _important_keywords(text: str) -> list[str]:
    """Return searchable terms, keeping short project abbreviations."""

    keywords: list[str] = []
    seen_keywords: set[str] = set()
    for word in re.findall(r"[a-zA-Z0-9_/-]{2,}", text.lower()):
        if word in KEYWORD_STOP_WORDS:
            continue
        if len(word) < 3 and word not in {"db", "pr"}:
            continue
        if word in seen_keywords:
            continue
        seen_keywords.add(word)
        keywords.append(word)
    return keywords


def _merge_and_rank_matches(
    semantic_matches: list[DocumentChunkMatch],
    keyword_matches: list[DocumentChunkMatch],
    question: str,
    max_matches: int,
) -> list[DocumentChunkMatch]:
    """Dedupe and rank matches using generic document signals."""

    if max_matches <= 0:
        return []

    query_keywords = _important_keywords(question)
    authority_question = _is_authority_question(question)
    ranked_by_chunk_id: dict[UUID, RankedMatch] = {}
    for index, match in enumerate([*semantic_matches, *keyword_matches]):
        ranked_match = _rank_match(
            match=match,
            index=index,
            query_keywords=query_keywords,
            authority_question=authority_question,
        )
        existing = ranked_by_chunk_id.get(match.chunk.id)
        if existing is not None and (
            existing.score > ranked_match.score
            or (existing.score == ranked_match.score and existing.index <= index)
        ):
            continue
        ranked_by_chunk_id[match.chunk.id] = ranked_match

    ranked_matches = sorted(
        ranked_by_chunk_id.values(),
        key=lambda item: (-item.score, item.index),
    )
    ranked_matches = _prefer_authoritative_matches(ranked_matches, authority_question)
    return [item.match for item in ranked_matches[:max_matches]]


def _retrieval_candidate_limit() -> int:
    """Fetch more than the final context size so re-ranking has room to work."""

    return max(settings.rag_top_k, 0) * RETRIEVAL_CANDIDATE_MULTIPLIER


def _rank_match(
    match: DocumentChunkMatch,
    index: int,
    query_keywords: list[str],
    authority_question: bool,
) -> RankedMatch:
    """Score a match using semantic, lexical, metadata, and authority signals."""

    ranking_content = _limited_chunk_text(match.chunk.content)
    chunk_overlap = _text_overlap_score(query_keywords, ranking_content)
    phrase_overlap = _phrase_overlap_score(query_keywords, ranking_content)
    metadata_overlap = _text_overlap_score(query_keywords, _match_metadata_text(match))
    authority_score = (
        _source_authority_score(match, chunk_overlap, phrase_overlap)
        if authority_question
        else 0
    )
    score = (
        match.similarity_score
        + (chunk_overlap * CHUNK_LEXICAL_WEIGHT)
        + (phrase_overlap * EXACT_PHRASE_WEIGHT)
        + (metadata_overlap * METADATA_LEXICAL_WEIGHT)
        + authority_score
    )
    return RankedMatch(
        score=score,
        index=index,
        match=match,
        chunk_overlap=chunk_overlap,
        phrase_overlap=phrase_overlap,
        metadata_overlap=metadata_overlap,
        authority_score=authority_score,
    )


def _prefer_authoritative_matches(
    ranked_matches: list[RankedMatch],
    authority_question: bool,
) -> list[RankedMatch]:
    """For standards questions, favor authoritative docs with content evidence."""

    if not authority_question:
        return ranked_matches
    authoritative_matches = [
        ranked_match
        for ranked_match in ranked_matches
        if ranked_match.authority_score >= AUTHORITY_SOURCE_WEIGHT
        and (ranked_match.chunk_overlap > 0 or ranked_match.phrase_overlap > 0)
    ]
    if not authoritative_matches:
        return ranked_matches
    return authoritative_matches


def _text_overlap_score(query_keywords: list[str], text: str) -> float:
    """Return how much of the question's important wording appears in text."""

    if not query_keywords:
        return 0
    text_keywords = set(_important_keywords(text))
    if not text_keywords:
        return 0
    matched_keywords = set(query_keywords).intersection(text_keywords)
    return len(matched_keywords) / len(set(query_keywords))


def _phrase_overlap_score(query_keywords: list[str], text: str) -> float:
    """Return adjacent-query-phrase overlap with the candidate text."""

    if len(query_keywords) < 2:
        return 0
    query_phrases = {
        f"{query_keywords[index]} {query_keywords[index + 1]}"
        for index in range(len(query_keywords) - 1)
    }
    text_keywords = _important_keywords(text)
    text_phrases = {
        f"{text_keywords[index]} {text_keywords[index + 1]}"
        for index in range(len(text_keywords) - 1)
    }
    if not text_phrases:
        return 0
    matched_phrases = query_phrases.intersection(text_phrases)
    return len(matched_phrases) / len(query_phrases)


def _is_authority_question(question: str) -> bool:
    """Return whether the user is asking for a rule, standard, or guidance."""

    return bool(set(_raw_terms(question)).intersection(AUTHORITY_QUERY_TERMS))


def _source_authority_score(
    match: DocumentChunkMatch,
    chunk_overlap: float,
    phrase_overlap: float,
) -> float:
    """Score whether the source looks like a standard, policy, or guideline."""

    metadata_terms = set(_raw_terms(_match_metadata_text(match)))
    if metadata_terms.intersection(AUTHORITY_SOURCE_TERMS):
        return AUTHORITY_SOURCE_WEIGHT
    if chunk_overlap > 0 or phrase_overlap > 0:
        content_terms = set(_raw_terms(_limited_chunk_text(match.chunk.content)))
        if content_terms.intersection(AUTHORITY_SOURCE_TERMS):
            return CONTENT_AUTHORITY_WEIGHT
    return 0


def _match_metadata_text(match: DocumentChunkMatch) -> str:
    """Return document-level metadata that can help rank any category."""

    category_name = _match_category(match)
    file_name = getattr(match.document, "file_name", "") or ""
    return f"{match.document.title} {category_name} {file_name}"


def _limited_chunk_text(content: str) -> str:
    """Limit ranking text so very long chunks do not dominate lexical scoring."""

    return " ".join(content.split()[:MAX_RANKING_CONTENT_WORDS])


def _raw_terms(text: str) -> list[str]:
    """Return lower-cased terms without stop-word filtering."""

    return re.findall(r"[a-zA-Z0-9_/-]{2,}", text.lower())


def _match_category(match: DocumentChunkMatch) -> str:
    """Return the category name for a match, tolerating incomplete ORM objects."""

    category = getattr(match.document, "category", None)
    return getattr(category, "name", "") or ""


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
