from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.ai import AI_RUN_STATUS_FAILED, AI_RUN_STATUS_SUCCESS
from app.constants.chat import CHAT_ROLE_ASSISTANT, CHAT_ROLE_USER
from app.core.config import settings
from app.core.prompts import SYSTEM_PROMPT
from app.models.database import ChatMessage, ChatSession
from app.repositories.chat import chat_repository
from app.schemas.chat.schemas import (
    ChatResponse,
    ChatSessionDetailResponse,
    ChatSessionListResponse,
    ChatSessionResponse,
    chat_message_to_response,
    chat_session_to_response,
)
from app.services.ai import AIProviderError
from app.services.ai.factory import create_ai_provider
from app.services.ask.service import NOT_AVAILABLE_ANSWER
from app.services.ask.context import build_context
from app.services.chat.exceptions import ChatSessionNotFoundError


class ChatService:
    """Business logic for authenticated multi-turn chat."""

    async def chat(
        self,
        db: AsyncSession,
        user_id: UUID,
        question: str,
        session_id: UUID | None = None,
        title: str | None = None,
        is_admin: bool = False,
    ) -> ChatResponse:
        """Answer a question in a user-owned chat session."""

        provider = create_ai_provider()
        session = await self._get_or_create_session(
            db=db,
            user_id=user_id,
            session_id=session_id,
            title=title,
            question=question,
        )
        history = await chat_repository.list_recent_messages(
            db,
            session.id,
            settings.chat_history_limit,
        )
        user_message = await chat_repository.create_message(
            db,
            session.id,
            CHAT_ROLE_USER,
            question.strip(),
        )

        document_context = await build_context(
            db,
            user_id=user_id,
            include_all=is_admin,
        )
        if not document_context.content:
            answer = NOT_AVAILABLE_ANSWER
            assistant_message = await chat_repository.create_message(
                db,
                session.id,
                CHAT_ROLE_ASSISTANT,
                answer,
            )
            await chat_repository.create_ai_run(
                db=db,
                session_id=session.id,
                model_name=provider.model_name,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                status=AI_RUN_STATUS_SUCCESS,
            )
            return ChatResponse(
                session_id=session.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                answer=answer,
                sources=[],
                model_used=provider.model_name,
            )

        user_prompt = self._build_user_prompt(
            document_context=document_context.content,
            history=history,
            question=question,
        )
        try:
            answer = await provider.chat(system=SYSTEM_PROMPT, user=user_prompt)
        except AIProviderError as exc:
            await chat_repository.create_ai_run(
                db=db,
                session_id=session.id,
                model_name=provider.model_name,
                user_message_id=user_message.id,
                assistant_message_id=None,
                status=AI_RUN_STATUS_FAILED,
                error_message=str(exc),
            )
            raise

        assistant_message = await chat_repository.create_message(
            db,
            session.id,
            CHAT_ROLE_ASSISTANT,
            answer or NOT_AVAILABLE_ANSWER,
        )
        await chat_repository.create_message_sources(
            db,
            assistant_message.id,
            document_context.source_ids,
        )
        await chat_repository.create_ai_run(
            db=db,
            session_id=session.id,
            model_name=provider.model_name,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            status=AI_RUN_STATUS_SUCCESS,
        )
        return ChatResponse(
            session_id=session.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            answer=answer or NOT_AVAILABLE_ANSWER,
            sources=document_context.source_names,
            model_used=provider.model_name,
        )

    async def list_sessions(
        self,
        db: AsyncSession,
        user_id: UUID,
        page: int,
        page_size: int,
    ) -> ChatSessionListResponse:
        """List sessions owned by the current user."""

        sessions, total = await chat_repository.list_sessions_for_user(
            db,
            user_id,
            page,
            page_size,
        )
        return ChatSessionListResponse(
            items=[chat_session_to_response(session) for session in sessions],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_session(
        self,
        db: AsyncSession,
        user_id: UUID,
        session_id: UUID,
    ) -> ChatSessionDetailResponse:
        """Return one user-owned session with messages."""

        session = await chat_repository.get_session_detail_for_user(
            db,
            session_id,
            user_id,
        )
        if session is None:
            raise ChatSessionNotFoundError("Chat session not found.")
        messages = sorted(session.messages, key=lambda message: message.created_at)
        response = chat_session_to_response(session)
        return ChatSessionDetailResponse(
            id=response.id,
            title=response.title,
            created_at=response.created_at,
            updated_at=response.updated_at,
            messages=[chat_message_to_response(message) for message in messages],
        )

    async def delete_session(
        self,
        db: AsyncSession,
        user_id: UUID,
        session_id: UUID,
    ) -> None:
        """Delete one user-owned chat session."""

        deleted = await chat_repository.delete_session_for_user(
            db,
            session_id,
            user_id,
        )
        if not deleted:
            raise ChatSessionNotFoundError("Chat session not found.")

    async def _get_or_create_session(
        self,
        db: AsyncSession,
        user_id: UUID,
        session_id: UUID | None,
        title: str | None,
        question: str,
    ) -> ChatSession:
        """Load a user-owned session or create a new one."""

        if session_id is not None:
            session = await chat_repository.get_session_for_user(
                db,
                session_id,
                user_id,
            )
            if session is None:
                raise ChatSessionNotFoundError("Chat session not found.")
            return session

        session_title = title or question.strip()[:80]
        return await chat_repository.create_session(
            db,
            user_id,
            session_title,
        )

    @staticmethod
    def _build_user_prompt(
        document_context: str,
        history: list[ChatMessage],
        question: str,
    ) -> str:
        """Build the long-context prompt with recent conversation history."""

        history_text = "\n".join(
            f"{message.role.upper()}: {message.content.strip()}"
            for message in history
            if message.content.strip()
        )
        if not history_text:
            history_text = "No previous messages."
        return (
            "DOCUMENT CONTEXT:\n"
            f"{document_context}\n\n"
            "CONVERSATION HISTORY:\n"
            f"{history_text}\n\n"
            "CURRENT USER QUESTION:\n"
            f"{question.strip()}"
        )
