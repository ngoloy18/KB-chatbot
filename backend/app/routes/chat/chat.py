from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.auth import USER_ROLE_ADMIN
from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.database import User
from app.schemas.chat.schemas import (
    ChatRequest,
    ChatResponse,
    ChatSessionDetailResponse,
    ChatSessionListResponse,
)
from app.services.ai import AIProviderConfigurationError, AIProviderError
from app.services.chat import chat_service
from app.services.chat.exceptions import ChatSessionNotFoundError


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    summary="Ask a multi-turn chat question",
    description="Answer a question inside a user-owned chat session.",
)
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    """Create or continue a user-owned chat session."""

    try:
        return await chat_service.chat(
            db=db,
            user_id=current_user.id,
            question=payload.question,
            session_id=payload.session_id,
            title=payload.title,
            is_admin=current_user.role == USER_ROLE_ADMIN,
        )
    except ChatSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AIProviderConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except AIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get(
    "/sessions",
    response_model=ChatSessionListResponse,
    summary="List my chat sessions",
)
async def list_chat_sessions(
    page: int = Query(default=DEFAULT_PAGE, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatSessionListResponse:
    """Return only sessions owned by the authenticated user."""

    return await chat_service.list_sessions(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionDetailResponse,
    summary="Get one of my chat sessions",
)
async def get_chat_session(
    session_id: UUID,
    page: int = Query(default=DEFAULT_PAGE, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatSessionDetailResponse:
    """Return one session only if it belongs to the authenticated user."""

    try:
        return await chat_service.get_session(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
            page=page,
            page_size=page_size,
        )
    except ChatSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one of my chat sessions",
)
async def delete_chat_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete one session only if it belongs to the authenticated user."""

    try:
        await chat_service.delete_session(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
        )
    except ChatSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
