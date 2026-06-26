from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prompts import SYSTEM_PROMPT
from app.schemas.ask.schemas import AskResponse
from app.services.ai.factory import create_ai_provider
from app.services.ask.context import build_context


NOT_AVAILABLE_ANSWER = "This information is not available in the current documents."


class AskService:
    """Business logic for long-context document Q&A."""

    async def ask(self, db: AsyncSession, question: str) -> AskResponse:
        """Answer one user question using the configured AI provider."""

        provider = create_ai_provider()
        document_context = await build_context(db)
        if not document_context.content:
            return AskResponse(
                answer=NOT_AVAILABLE_ANSWER,
                sources=[],
                model_used=provider.model_name,
            )

        user_prompt = self._build_user_prompt(document_context.content, question)
        answer = await provider.chat(system=SYSTEM_PROMPT, user=user_prompt)
        return AskResponse(
            answer=answer or NOT_AVAILABLE_ANSWER,
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
