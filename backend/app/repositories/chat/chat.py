from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import AIRun, ChatMessage, ChatSession, MessageSource


class ChatRepository:
    """SQLAlchemy queries for user-owned chat sessions and messages."""

    async def create_session(
        self,
        db: AsyncSession,
        user_id: UUID,
        title: str | None,
    ) -> ChatSession:
        """Create one chat session for a user."""

        session = ChatSession(user_id=user_id, title=title)
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def get_session_for_user(
        self,
        db: AsyncSession,
        session_id: UUID,
        user_id: UUID,
    ) -> ChatSession | None:
        """Return a session only when it belongs to the given user."""

        query = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
        return await db.scalar(query)

    async def get_session_detail_for_user(
        self,
        db: AsyncSession,
        session_id: UUID,
        user_id: UUID,
    ) -> ChatSession | None:
        """Return a user-owned session for a detail view."""

        query = (
            select(ChatSession)
            .where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
        )
        return await db.scalar(query)

    async def list_messages_for_session(
        self,
        db: AsyncSession,
        session_id: UUID,
        page: int,
        page_size: int,
    ) -> tuple[list[ChatMessage], int]:
        """Return one page from the newest messages, ordered for display."""

        filters = [ChatMessage.session_id == session_id]
        total = await db.scalar(
            select(func.count()).select_from(ChatMessage).where(*filters)
        )
        query = (
            select(ChatMessage)
            .where(*filters)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = list((await db.scalars(query)).all())
        rows.reverse()
        return rows, total or 0

    async def list_sessions_for_user(
        self,
        db: AsyncSession,
        user_id: UUID,
        page: int,
        page_size: int,
    ) -> tuple[list[ChatSession], int]:
        """Return one page of chat sessions owned by a user."""

        filters = [ChatSession.user_id == user_id]
        total = await db.scalar(
            select(func.count()).select_from(ChatSession).where(*filters)
        )
        query = (
            select(ChatSession)
            .where(*filters)
            .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = await db.scalars(query)
        return list(rows), total or 0

    async def delete_session_for_user(
        self,
        db: AsyncSession,
        session_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Delete a session only when it belongs to the given user."""

        result = await db.execute(
            delete(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
        )
        await db.commit()
        return (result.rowcount or 0) > 0

    async def create_message(
        self,
        db: AsyncSession,
        session_id: UUID,
        role: str,
        content: str,
    ) -> ChatMessage:
        """Create one chat message in a session."""

        message = ChatMessage(session_id=session_id, role=role, content=content)
        db.add(message)
        await db.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(updated_at=func.now())
        )
        await db.commit()
        await db.refresh(message)
        return message

    async def list_recent_messages(
        self,
        db: AsyncSession,
        session_id: UUID,
        limit: int,
    ) -> list[ChatMessage]:
        """Return recent messages oldest-first for prompt history."""

        query = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        rows = list((await db.scalars(query)).all())
        rows.reverse()
        return rows

    async def create_ai_run(
        self,
        db: AsyncSession,
        session_id: UUID,
        model_name: str,
        user_message_id: UUID | None,
        assistant_message_id: UUID | None,
        status: str,
        error_message: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ) -> AIRun:
        """Record metadata for one AI provider call."""

        run = AIRun(
            session_id=session_id,
            model_name=model_name,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            status=status,
            error_message=error_message,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run

    async def create_chunk_message_sources(
        self,
        db: AsyncSession,
        message_id: UUID,
        sources: list[tuple[UUID, UUID, float | None]],
    ) -> list[MessageSource]:
        """Attach retrieved chunk citations to an assistant message."""

        message_sources = [
            MessageSource(
                message_id=message_id,
                document_id=document_id,
                chunk_id=chunk_id,
                similarity_score=similarity_score,
            )
            for document_id, chunk_id, similarity_score in sources
        ]
        db.add_all(message_sources)
        await db.commit()
        return message_sources


chat_repository = ChatRepository()
