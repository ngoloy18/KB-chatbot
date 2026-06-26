from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import DocumentCategory
from app.repositories.documents.documents import document_repository


CONTEXT_CATEGORIES = (
    DocumentCategory.CODING_CONVENTION,
    DocumentCategory.GIT_FLOW,
    DocumentCategory.PULL_REQUEST,
    DocumentCategory.DATABASE,
    DocumentCategory.API_STANDARD,
    DocumentCategory.LOGGING,
)


@dataclass(frozen=True)
class ContextSource:
    """Source document metadata included in a prompt."""

    document_id: UUID
    name: str
    category: str


@dataclass(frozen=True)
class DocumentContext:
    """Cached long-context document payload and source names."""

    content: str
    sources: list[ContextSource]

    @property
    def source_names(self) -> list[str]:
        """Return unique source names in prompt order."""

        names: list[str] = []
        for source in self.sources:
            if source.name not in names:
                names.append(source.name)
        return names

    @property
    def source_ids(self) -> list[UUID]:
        """Return source document IDs in prompt order."""

        return [source.document_id for source in self.sources]


_CONTEXT_CACHE: dict[tuple[bool, str | None], DocumentContext] = {}


async def build_context(
    db: AsyncSession,
    user_id: UUID | None = None,
    include_all: bool = True,
) -> DocumentContext:
    """Build or return cached context for the engineering standards documents."""

    cache_key = (include_all, None if include_all else str(user_id))
    if cache_key in _CONTEXT_CACHE:
        return _CONTEXT_CACHE[cache_key]

    if not include_all and user_id is None:
        empty_context = DocumentContext(content="", sources=[])
        _CONTEXT_CACHE[cache_key] = empty_context
        return empty_context

    documents = await document_repository.list_documents_for_context(
        db,
        CONTEXT_CATEGORIES,
        user_id=user_id,
        include_all=include_all,
    )
    blocks: list[str] = []
    sources: list[ContextSource] = []
    for document in documents:
        source_name = document.title
        blocks.append(
            (
                f"=== {source_name} ({document.category.name}) ===\n"
                f"{document.content.strip()}"
            )
        )
        sources.append(
            ContextSource(
                document_id=document.id,
                name=source_name,
                category=document.category.name,
            )
        )

    document_context = DocumentContext(
        content="\n\n".join(blocks),
        sources=sources,
    )
    _CONTEXT_CACHE[cache_key] = document_context
    return document_context


def invalidate_context_cache() -> None:
    """Force the next ask request to reload document context from the database."""

    _CONTEXT_CACHE.clear()
