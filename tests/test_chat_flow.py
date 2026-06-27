import asyncio
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, func, select

# Add the project root to Python's import path when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import app.services.chat.service as chat_service_module
import app.services.chat.retrieval as retrieval_module
import app.services.documents.service as document_service_module
from app.constants.ai import AI_RUN_STATUS_FAILED
from app.constants.permissions import DOCUMENT_PERMISSION_READ
from app.core.config import DocumentCategory, settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.database import AIRun, Document, User
from app.repositories.users.users import user_repository
from app.schemas.documents.schemas import (
    DocumentCreate,
    DocumentPermissionUpsertRequest,
    DocumentPermissionValue,
)
from app.services import document_service
from app.services.ai import AIProviderError
from app.services.ask import invalidate_context_cache
from app.services.ask.service import NOT_AVAILABLE_ANSWER
from app.services.chat import chat_service


class StubAIProvider:
    """Small in-memory provider so tests do not call external AI services."""

    def __init__(self, answer: str = "stub answer", should_fail: bool = False) -> None:
        self.model_name = "stub-test-model"
        self.answer = answer
        self.should_fail = should_fail
        self.prompts: list[str] = []

    async def chat(self, system: str, user: str) -> str:
        self.prompts.append(user)
        if self.should_fail:
            raise AIProviderError("stub provider failed")
        return self.answer


class StubEmbeddingProvider:
    """Deterministic embedding provider for local semantic retrieval tests."""

    provider_name = "stub"
    model_name = "stub-embedding-model"

    async def embed_query(self, query: str) -> list[float]:
        return self._vector_for_text(query)

    async def embed_documents(self, documents) -> list[list[float]]:
        return [self._vector_for_text(document.content) for document in documents]

    @staticmethod
    def _vector_for_text(text: str) -> list[float]:
        lowered_text = text.lower()
        if "denied" in lowered_text:
            return [0.0, 1.0, 0.0]
        return [1.0, 0.0, 0.0]


async def create_test_user(db, email: str) -> User:
    """Create a verified user for service-level chat tests."""

    return await user_repository.create_user(
        db=db,
        email=email,
        hashed_password=hash_password("Password123!"),
        is_email_verified=True,
    )


async def create_test_document(db, name: str, content: str) -> Document:
    """Create a ready document through the service so chunks/versions are valid."""

    response = await document_service.create_document(
        db,
        DocumentCreate(
            name=name,
            category=DocumentCategory.API_STANDARD,
            content=content,
            file_name=f"{name}.md",
            file_path=f"uploads/{name}.md",
            file_type="text/markdown",
        ),
    )
    return await document_service._get_document_or_raise(db, response.id)


async def grant_read(db, document: Document, user: User) -> None:
    """Allow one normal user to read one document."""

    await document_service.grant_document_permission(
        db,
        document.id,
        DocumentPermissionUpsertRequest(
            user_id=user.id,
            permission=DocumentPermissionValue(DOCUMENT_PERMISSION_READ),
        ),
    )
    invalidate_context_cache()


def use_stub_provider(provider: StubAIProvider):
    """Replace the chat provider factory and return the original callable."""

    original_factory = chat_service_module.create_ai_provider
    chat_service_module.create_ai_provider = lambda: provider
    return original_factory


async def check_chat_flow() -> None:
    """Verify chat happy path, no docs, permission filtering, and provider failure."""

    suffix = uuid4().hex[:8]
    user_email = f"chat_user_{suffix}@example.com"
    no_docs_email = f"chat_nodocs_{suffix}@example.com"
    failure_email = f"chat_failure_{suffix}@example.com"
    doc_prefix = f"chat-flow-{suffix}"
    user_emails = [user_email, no_docs_email, failure_email]
    document_names = [
        f"{doc_prefix}-happy",
        f"{doc_prefix}-allowed",
        f"{doc_prefix}-denied",
        f"{doc_prefix}-failure",
    ]
    original_factory = chat_service_module.create_ai_provider
    original_document_embedding_factory = document_service_module.create_embedding_provider
    original_retrieval_embedding_factory = retrieval_module.create_embedding_provider
    original_embeddings_enabled = settings.embeddings_enabled
    original_rag_min_similarity = settings.rag_min_similarity
    original_rag_top_k = settings.rag_top_k
    original_rag_max_context_tokens = settings.rag_max_context_tokens

    async with AsyncSessionLocal() as db:
        try:
            embedding_provider = StubEmbeddingProvider()
            settings.embeddings_enabled = True
            settings.rag_min_similarity = 0.8
            settings.rag_top_k = 5
            settings.rag_max_context_tokens = 1800
            document_service_module.create_embedding_provider = (
                lambda: embedding_provider
            )
            retrieval_module.create_embedding_provider = lambda: embedding_provider

            user = await create_test_user(db, user_email)
            no_docs_user = await create_test_user(db, no_docs_email)
            failure_user = await create_test_user(db, failure_email)

            happy_doc = await create_test_document(
                db,
                document_names[0],
                f"Happy path unique context {suffix}.",
            )
            allowed_doc = await create_test_document(
                db,
                document_names[1],
                f"Allowed user context {suffix}.",
            )
            denied_doc = await create_test_document(
                db,
                document_names[2],
                f"Denied user context {suffix}.",
            )
            failure_doc = await create_test_document(
                db,
                document_names[3],
                f"Failure test context {suffix}.",
            )

            await grant_read(db, allowed_doc, user)
            await grant_read(db, failure_doc, failure_user)

            happy_provider = StubAIProvider(answer="happy answer")
            original_factory = use_stub_provider(happy_provider)
            happy_response = await chat_service.chat(
                db=db,
                user_id=user.id,
                question=f"What says allowed context {suffix}?",
                is_admin=False,
            )
            if happy_response.answer != "happy answer":
                raise AssertionError("Chat happy path should return provider answer.")
            if happy_response.model_used != happy_provider.model_name:
                raise AssertionError("Chat should return the provider model name.")
            if allowed_doc.title not in happy_response.sources:
                raise AssertionError("Chat should cite the visible source document.")

            no_docs_provider = StubAIProvider(answer="should not be called")
            chat_service_module.create_ai_provider = lambda: no_docs_provider
            no_docs_response = await chat_service.chat(
                db=db,
                user_id=no_docs_user.id,
                question=f"What says unavailable context {suffix}?",
                is_admin=False,
            )
            if no_docs_response.answer != NOT_AVAILABLE_ANSWER:
                raise AssertionError("Chat without visible docs should not hallucinate.")
            if no_docs_response.sources:
                raise AssertionError("Chat without visible docs should return no sources.")
            if no_docs_provider.prompts:
                raise AssertionError("Provider should not be called without visible docs.")

            filtered_provider = StubAIProvider(answer="filtered answer")
            chat_service_module.create_ai_provider = lambda: filtered_provider
            filtered_response = await chat_service.chat(
                db=db,
                user_id=user.id,
                question=f"Which docs are visible {suffix}?",
                is_admin=False,
            )
            filtered_prompt = filtered_provider.prompts[-1]
            if f"Allowed user context {suffix}" not in filtered_prompt:
                raise AssertionError("Permitted document should be in chat context.")
            if f"Denied user context {suffix}" in filtered_prompt:
                raise AssertionError("Unpermitted document leaked into chat context.")
            if denied_doc.title in filtered_response.sources:
                raise AssertionError("Unpermitted document should not be cited.")

            failing_provider = StubAIProvider(should_fail=True)
            chat_service_module.create_ai_provider = lambda: failing_provider
            try:
                await chat_service.chat(
                    db=db,
                    user_id=failure_user.id,
                    question=f"Trigger provider failure {suffix}",
                    is_admin=False,
                )
            except AIProviderError:
                pass
            else:
                raise AssertionError("Chat should raise AIProviderError on provider failure.")

            failed_runs = await db.scalar(
                select(func.count())
                .select_from(AIRun)
                .where(
                    AIRun.model_name == failing_provider.model_name,
                    AIRun.status == AI_RUN_STATUS_FAILED,
                    AIRun.error_message.ilike("%stub provider failed%"),
                )
            )
            if failed_runs != 1:
                raise AssertionError("Provider failures should be recorded in ai_runs.")
        finally:
            chat_service_module.create_ai_provider = original_factory
            document_service_module.create_embedding_provider = (
                original_document_embedding_factory
            )
            retrieval_module.create_embedding_provider = (
                original_retrieval_embedding_factory
            )
            settings.embeddings_enabled = original_embeddings_enabled
            settings.rag_min_similarity = original_rag_min_similarity
            settings.rag_top_k = original_rag_top_k
            settings.rag_max_context_tokens = original_rag_max_context_tokens
            invalidate_context_cache()
            await db.rollback()
            await db.execute(delete(Document).where(Document.title.in_(document_names)))
            await db.execute(delete(User).where(User.email.in_(user_emails)))
            await db.commit()
            invalidate_context_cache()

    print("Chat flow OK.")


if __name__ == "__main__":
    try:
        asyncio.run(check_chat_flow())
    except Exception as exc:
        print("Chat flow test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
