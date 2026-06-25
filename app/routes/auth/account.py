from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth.schemas import (
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.auth.exceptions import (
    DuplicateEmailError,
    InvalidVerificationTokenError,
)
from app.services.auth.service import auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a normal user",
)
async def register_user(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """Register a normal user account; public registration never creates admins."""

    try:
        # The service owns registration rules; the route only converts errors to HTTP.
        return await auth_service.register_user(db, payload)
    except DuplicateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/verify-email",
    response_model=UserResponse,
    summary="Verify registered email",
)
async def verify_email(
    payload: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Verify an email address using the registration verification token."""

    try:
        return await auth_service.verify_email(db, payload)
    except InvalidVerificationTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/resend-verification",
    response_model=ResendVerificationResponse,
    summary="Resend email verification",
)
async def resend_verification(
    payload: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
) -> ResendVerificationResponse:
    """Request a fresh email verification token for an unverified account."""

    return await auth_service.resend_verification(db, payload)
