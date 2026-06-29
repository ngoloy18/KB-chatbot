import asyncio
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete

# Add the project root to Python's import path when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import app.services.ask.service as ask_service_module
from app.constants.permissions import DOCUMENT_PERMISSION_READ
from app.core.config import DocumentCategory, settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.database import Document, User
from app.repositories.users.users import user_repository
from app.schemas.documents.schemas import (
    DocumentCreate,
    DocumentPermissionUpsertRequest,
    DocumentPermissionValue,
)
from app.services import document_service
from app.services.ai import AIProviderError, AIResponse
from app.services.ask import ask_service
from app.services.ask.constants import NOT_AVAILABLE_ANSWER


class StubAIProvider:
    """Small provider stub so ask-flow tests never call Gemini."""

    def __init__(
        self,
        answer: str = "stub ask answer",
        should_fail: bool = False,
    ) -> None:
        self.model_name = "stub-ask-model"
        self.answer = answer
        self.should_fail = should_fail
        self.prompts: list[str] = []

    async def chat(self, system: str, user: str) -> str:
        response = await self.chat_with_usage(system=system, user=user)
        return response.text

    async def chat_with_usage(self, system: str, user: str) -> AIResponse:
        self.prompts.append(user)
        if self.should_fail:
            raise AIProviderError("stub ask provider failed")
        return AIResponse(
            text=self.answer,
            prompt_tokens=9,
            completion_tokens=4,
            total_tokens=13,
        )


async def create_test_user(db, email: str) -> User:
    """Create a verified normal user for ask service tests."""

    return await user_repository.create_user(
        db=db,
        email=email,
        hashed_password=hash_password("Password123!"),
        is_email_verified=True,
    )


async def create_test_document(db, name: str, content: str) -> Document:
    """Create a ready document through the service so chunks exist."""

    response = await document_service.create_document(
        db,
        DocumentCreate(
            name=name,
            category=DocumentCategory.PULL_REQUEST,
            content=content,
            file_name=f"{name}.md",
            file_path=f"uploads/{name}.md",
            file_type="text/markdown",
        ),
    )
    return await document_service._get_document_or_raise(db, response.id)


async def grant_read(db, document: Document, user: User) -> None:
    """Grant read permission for one user/document pair."""

    await document_service.grant_document_permission(
        db=db,
        document_id=document.id,
        payload=DocumentPermissionUpsertRequest(
            user_id=user.id,
            permission=DocumentPermissionValue(DOCUMENT_PERMISSION_READ),
        ),
    )


def use_stub_provider(provider: StubAIProvider):
    """Replace the ask provider factory and return the original callable."""

    original_factory = ask_service_module.create_ai_provider
    ask_service_module.create_ai_provider = lambda: provider
    return original_factory


async def check_ask_flow() -> None:
    """Verify ask happy path, no docs, permissions, and provider failure."""

    suffix = uuid4().hex[:8]
    user_email = f"ask_user_{suffix}@example.com"
    no_docs_email = f"ask_nodocs_{suffix}@example.com"
    failure_email = f"ask_failure_{suffix}@example.com"
    doc_prefix = f"ask-flow-{suffix}"
    user_emails = [user_email, no_docs_email, failure_email]
    document_names = [
        f"{doc_prefix}-happy",
        f"{doc_prefix}-allowed",
        f"{doc_prefix}-denied",
        f"{doc_prefix}-failure",
    ]

    original_factory = ask_service_module.create_ai_provider
    original_embeddings_enabled = settings.embeddings_enabled
    original_rag_top_k = settings.rag_top_k
    original_rag_max_context_tokens = settings.rag_max_context_tokens

    async with AsyncSessionLocal() as db:
        try:
            settings.embeddings_enabled = False
            settings.rag_top_k = 5
            settings.rag_max_context_tokens = 1800

            user = await create_test_user(db, user_email)
            no_docs_user = await create_test_user(db, no_docs_email)
            failure_user = await create_test_user(db, failure_email)

            happy_phrase = f"happy-ask-question-{suffix}"
            shared_phrase = f"shared-ask-question-{suffix}"
            failure_phrase = f"failure-ask-question-{suffix}"

            happy_doc = await create_test_document(
                db,
                document_names[0],
                f"Pull request guidance for {happy_phrase}: include summary and tests.",
            )
            allowed_doc = await create_test_document(
                db,
                document_names[1],
                f"Allowed document content for {shared_phrase}.",
            )
            denied_doc = await create_test_document(
                db,
                document_names[2],
                f"Denied document content for {shared_phrase}.",
            )
            failure_doc = await create_test_document(
                db,
                document_names[3],
                f"Failure document content for {failure_phrase}.",
            )

            await grant_read(db, happy_doc, user)
            await grant_read(db, allowed_doc, user)
            await grant_read(db, failure_doc, failure_user)

            happy_provider = StubAIProvider(answer="happy ask answer")
            original_factory = use_stub_provider(happy_provider)
            happy_response = await ask_service.ask(
                db=db,
                question=happy_phrase,
                user_id=user.id,
                is_admin=False,
            )
            if happy_response.answer != "happy ask answer":
                raise AssertionError("Ask happy path should return provider answer.")
            if happy_response.model_used != happy_provider.model_name:
                raise AssertionError("Ask should return the provider model name.")
            if happy_doc.title not in happy_response.sources:
                raise AssertionError("Ask should cite the visible source document.")
            if (
                f"Pull request guidance for {happy_phrase}"
                not in happy_provider.prompts[-1]
            ):
                raise AssertionError("Ask prompt should include matching document context.")

            no_docs_provider = StubAIProvider(answer="should not be called")
            ask_service_module.create_ai_provider = lambda: no_docs_provider
            no_docs_response = await ask_service.ask(
                db=db,
                question=f"missing-ask-question-{suffix}",
                user_id=no_docs_user.id,
                is_admin=False,
            )
            if no_docs_response.answer != NOT_AVAILABLE_ANSWER:
                raise AssertionError("Ask without matching docs should not hallucinate.")
            if no_docs_response.sources:
                raise AssertionError("Ask without matching docs should return no sources.")
            if no_docs_provider.prompts:
                raise AssertionError("Provider should not be called without context.")

            filtered_provider = StubAIProvider(answer="filtered ask answer")
            ask_service_module.create_ai_provider = lambda: filtered_provider
            filtered_response = await ask_service.ask(
                db=db,
                question=shared_phrase,
                user_id=user.id,
                is_admin=False,
            )
            filtered_prompt = filtered_provider.prompts[-1]
            if f"Allowed document content for {shared_phrase}" not in filtered_prompt:
                raise AssertionError("Permitted document should be in ask context.")
            if f"Denied document content for {shared_phrase}" in filtered_prompt:
                raise AssertionError("Unpermitted document leaked into ask context.")
            if allowed_doc.title not in filtered_response.sources:
                raise AssertionError("Ask should cite the permitted document.")
            if denied_doc.title in filtered_response.sources:
                raise AssertionError("Ask should not cite unpermitted documents.")

            failing_provider = StubAIProvider(should_fail=True)
            ask_service_module.create_ai_provider = lambda: failing_provider
            try:
                await ask_service.ask(
                    db=db,
                    question=failure_phrase,
                    user_id=failure_user.id,
                    is_admin=False,
                )
            except AIProviderError:
                pass
            else:
                raise AssertionError("Ask should raise AIProviderError on provider failure.")
        finally:
            ask_service_module.create_ai_provider = original_factory
            settings.embeddings_enabled = original_embeddings_enabled
            settings.rag_top_k = original_rag_top_k
            settings.rag_max_context_tokens = original_rag_max_context_tokens
            await db.rollback()
            await db.execute(delete(Document).where(Document.title.in_(document_names)))
            await db.execute(delete(User).where(User.email.in_(user_emails)))
            await db.commit()

    print("Ask flow OK.")


if __name__ == "__main__":
    try:
        asyncio.run(check_ask_flow())
    except Exception as exc:
        print("Ask flow test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
