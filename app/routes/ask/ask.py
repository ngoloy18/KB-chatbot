from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.auth import USER_ROLE_ADMIN
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.database import User
from app.schemas.ask.schemas import AskRequest, AskResponse
from app.services.ai import AIProviderConfigurationError, AIProviderError
from app.services.ask import ask_service


router = APIRouter(tags=["ask"])


@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask a document-grounded question",
    description="Answer a question from documents the authenticated user can read.",
)
async def ask_question(
    payload: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AskResponse:
    """Answer one question using the configured AI provider."""

    try:
        return await ask_service.ask(
            db=db,
            question=payload.question,
            user_id=current_user.id,
            is_admin=current_user.role == USER_ROLE_ADMIN,
        )
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
