from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth.schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    UserResponse,
)
from app.services.auth.exceptions import (
    InactiveUserError,
    InvalidPasswordResetTokenError,
)
from app.services.auth.service import auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Request password reset",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ForgotPasswordResponse:
    """Create a password reset token for a registered email address."""

    return await auth_service.forgot_password(db, payload)


@router.post(
    "/reset-password",
    response_model=UserResponse,
    summary="Reset password",
)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Replace a password using a valid password reset token."""

    try:
        return await auth_service.reset_password(db, payload)
    except InvalidPasswordResetTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
