from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.db.session import get_db
from app.dependencies.auth import require_admin
from app.models.database import User
from app.schemas.users.schemas import UserAdminResponse, UserListResponse, UserUpdateRequest
from app.services.auth.exceptions import DuplicateEmailError
from app.services.users.exceptions import CannotDeleteSelfError, UserNotFoundError
from app.services.users.service import user_service


router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "",
    response_model=UserListResponse,
    summary="List users as admin",
)
async def list_users(
    page: int = Query(default=DEFAULT_PAGE, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> UserListResponse:
    """Return users for admin management screens."""

    return await user_service.list_users(db, page, page_size)


@router.get(
    "/{user_id}",
    response_model=UserAdminResponse,
    summary="Get one user as admin",
)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> UserAdminResponse:
    """Return one user by id for admins."""

    try:
        return await user_service.get_user(db, user_id)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch(
    "/{user_id}",
    response_model=UserAdminResponse,
    summary="Update one user as admin",
)
async def update_user(
    user_id: UUID,
    payload: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> UserAdminResponse:
    """Update user profile, role, active status, verification, or password."""

    try:
        return await user_service.update_user(db, user_id, payload)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DuplicateEmailError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one user as admin",
)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> Response:
    """Delete a user account as admin."""

    try:
        await user_service.delete_user(db, user_id, current_admin.id)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except CannotDeleteSelfError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
