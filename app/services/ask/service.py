from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prompts import SYSTEM_PROMPT
from app.schemas.ask.schemas import AskResponse
from app.services.ai import call_chat_with_usage
from app.services.ai.factory import create_ai_provider
from app.services.ask.constants import NOT_AVAILABLE_ANSWER
from app.services.chat.retrieval import retrieve_chat_context


class AskService:
    """Business logic for long-context document Q&A."""

    async def ask(
        self,
        db: AsyncSession,
        question: str,
        user_id: UUID,
        is_admin: bool = False,
    ) -> AskResponse:
        """Answer one user question using the configured AI provider."""

        provider = create_ai_provider()
        document_context = await retrieve_chat_context(
            db=db,
            question=question,
            user_id=user_id,
            include_all=is_admin,
        )
        if not document_context.content:
            return AskResponse(
                answer=NOT_AVAILABLE_ANSWER,
                sources=[],
                model_used=provider.model_name,
            )

        user_prompt = self._build_user_prompt(document_context.content, question)
        ai_response = await call_chat_with_usage(
            provider=provider,
            system=SYSTEM_PROMPT,
            user=user_prompt,
        )
        return AskResponse(
            answer=ai_response.text or NOT_AVAILABLE_ANSWER,
            sources=document_context.source_names,
            model_used=provider.model_name,
        )

    @staticmethod
    def _build_user_prompt(document_context: str, question: str) -> str:
        """Combine cached document context and the user's question."""

        return (
            "DOCUMENT CONTEXT:\n"
            f"{document_context}\n\n"
            "USER QUESTION:\n"
            f"{question.strip()}"
        )
