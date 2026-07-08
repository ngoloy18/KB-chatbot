import sys
from pathlib import Path
from uuid import uuid4

# Add the project root to Python's import path when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import app.services.chat.retrieval as retrieval_module
from app.core.config import DocumentCategory
from app.models.database import Document, DocumentCategoryModel, DocumentChunk
from app.repositories.documents.documents import DocumentChunkMatch


def make_match(
    title: str,
    category_name: str,
    content: str,
    similarity_score: float,
) -> DocumentChunkMatch:
    """Build a lightweight chunk match without touching the database."""

    category = DocumentCategoryModel(id=uuid4(), name=category_name)
    document = Document(
        id=uuid4(),
        title=title,
        category=category,
        category_id=category.id,
        content=content,
    )
    chunk = DocumentChunk(
        id=uuid4(),
        document_id=document.id,
        chunk_index=0,
        content=content,
        token_count=len(content.split()),
    )
    return DocumentChunkMatch(
        chunk=chunk,
        document=document,
        similarity_score=similarity_score,
    )


def check_api_question_keyword_queries() -> None:
    """Verify retrieval searches the important API phrase, not filler words."""

    queries = retrieval_module._build_keyword_queries(
        "What HTTP method should be used to retrieve resources?"
    )
    query_texts = [query.text for query in queries]
    if "retrieve resources" not in query_texts:
        raise AssertionError("API retrieval should search the useful phrase.")
    if "should" in query_texts or "used" in query_texts:
        raise AssertionError("Keyword retrieval should skip filler words.")

    method_queries = retrieval_module._build_keyword_queries(
        "When should I use POST instead of PUT?"
    )
    method_query_texts = [query.text for query in method_queries]
    if "post" not in method_query_texts or "put" not in method_query_texts:
        raise AssertionError("Method comparison questions should search both methods.")
    if "use" in method_query_texts or "instead" in method_query_texts:
        raise AssertionError("Method comparison queries should skip filler words.")


def check_api_question_prefers_api_standard() -> None:
    """Verify a standards doc wins over a stronger example-only match."""

    api_match = make_match(
        title="API Standard",
        category_name=DocumentCategory.API_STANDARD.value,
        content="Use GET to retrieve resources.",
        similarity_score=0.7,
    )
    git_flow_match = make_match(
        title="Git Flow",
        category_name=DocumentCategory.GIT_FLOW.value,
        content="A Git Flow example mentions an HTTP GET request.",
        similarity_score=0.95,
    )
    ranked_matches = retrieval_module._merge_and_rank_matches(
        semantic_matches=[git_flow_match, api_match],
        keyword_matches=[],
        question="What HTTP method should be used to retrieve resources?",
        max_matches=10,
    )
    if ranked_matches != [api_match]:
        raise AssertionError(
            "Standards questions should keep normative docs instead of examples."
        )


def check_generic_authority_ranking() -> None:
    """Verify ranking works for categories the code does not know by name."""

    policy_match = make_match(
        title="Security Policy",
        category_name="security-policy",
        content="Password rules require at least 12 characters.",
        similarity_score=0.72,
    )
    example_match = make_match(
        title="Implementation Notes",
        category_name="misc",
        content="An example form accepts a password value.",
        similarity_score=0.95,
    )
    ranked_matches = retrieval_module._merge_and_rank_matches(
        semantic_matches=[example_match, policy_match],
        keyword_matches=[],
        question="What password rules should we use?",
        max_matches=10,
    )
    if ranked_matches != [policy_match]:
        raise AssertionError("Generic policy documents should rank above examples.")

    method_match = make_match(
        title="API Standard",
        category_name=DocumentCategory.API_STANDARD.value,
        content=(
            "Use POST to create resources. "
            "Use PUT to replace a resource when full replacement is supported."
        ),
        similarity_score=0.72,
    )
    notes_match = make_match(
        title="HTTP Examples",
        category_name="examples",
        content="This example mentions POST in a request payload.",
        similarity_score=0.95,
    )
    ranked_method_matches = retrieval_module._merge_and_rank_matches(
        semantic_matches=[notes_match, method_match],
        keyword_matches=[],
        question="When should I use POST instead of PUT?",
        max_matches=10,
    )
    if ranked_method_matches != [method_match]:
        raise AssertionError("Method guidance should prefer standards over examples.")


def main() -> None:
    """Run retrieval ranking checks."""

    check_api_question_keyword_queries()
    check_api_question_prefers_api_standard()
    check_generic_authority_ranking()
    print("Retrieval ranking OK.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Retrieval ranking test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
