from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.database import ChatMessage, ChatSession


class ChatRequest(BaseModel):
    """Question submitted to the authenticated multi-turn chat endpoint."""

    question: str = Field(..., min_length=1, max_length=1000)
    session_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)


class ChatResponse(BaseModel):
    """Assistant answer plus persisted message/session identifiers."""

    session_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID
    answer: str
    sources: list[str]
    model_used: str


class ChatSessionResponse(BaseModel):
    """One chat session owned by the current user."""

    id: UUID
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatSessionListResponse(BaseModel):
    """Paginated user-owned chat sessions."""

    items: list[ChatSessionResponse]
    total: int
    page: int
    page_size: int


class ChatMessageResponse(BaseModel):
    """One persisted chat message."""

    id: UUID
    role: str
    content: str
    created_at: datetime


class ChatSessionDetailResponse(ChatSessionResponse):
    """One user-owned chat session with its messages."""

    messages: list[ChatMessageResponse]


def chat_session_to_response(session: ChatSession) -> ChatSessionResponse:
    """Convert a ChatSession ORM object into a public response."""

    return ChatSessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def chat_message_to_response(message: ChatMessage) -> ChatMessageResponse:
    """Convert a ChatMessage ORM object into a public response."""

    return ChatMessageResponse(
        id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
    )
