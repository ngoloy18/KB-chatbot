from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.ask.schemas import AskRequest, AskResponse
from app.services.ai import AIProviderConfigurationError, AIProviderError
from app.services.ask import ask_service


router = APIRouter(tags=["ask"])


@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask a document-grounded question",
    description="Answer a question from the cached engineering standards context.",
)
async def ask_question(
    payload: AskRequest,
    db: AsyncSession = Depends(get_db),
) -> AskResponse:
    """Answer one question using the configured AI provider."""

    try:
        return await ask_service.ask(db=db, question=payload.question)
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
