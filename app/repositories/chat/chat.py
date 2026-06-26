from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
        """Return a user-owned session with messages loaded."""

        query = (
            select(ChatSession)
            .options(selectinload(ChatSession.messages))
            .where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
        )
        return await db.scalar(query)

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
    ) -> AIRun:
        """Record metadata for one AI provider call."""

        run = AIRun(
            session_id=session_id,
            model_name=model_name,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            status=status,
            error_message=error_message,
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run

    async def create_message_sources(
        self,
        db: AsyncSession,
        message_id: UUID,
        document_ids: list[UUID],
    ) -> list[MessageSource]:
        """Attach source document citations to an assistant message."""

        sources = [
            MessageSource(message_id=message_id, document_id=document_id)
            for document_id in document_ids
        ]
        db.add_all(sources)
        await db.commit()
        return sources


chat_repository = ChatRepository()
