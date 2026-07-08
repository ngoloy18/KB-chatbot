from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.db.session import get_db
from app.dependencies.auth import require_admin
from app.models.database import User
from app.schemas.users.schemas import (
    UserAdminResponse,
    UserCreateRequest,
    UserListResponse,
    UserUpdateRequest,
)
from app.services.audit import audit_service
from app.services.auth.exceptions import DuplicateEmailError
from app.services.users.exceptions import (
    CannotDeleteSelfError,
    CannotRemoveLastAdminError,
    UserNotFoundError,
)
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


@router.post(
    "",
    response_model=UserAdminResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create one user as admin",
)
async def create_user(
    payload: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> UserAdminResponse:
    """Create a user account from the admin management screen."""

    try:
        created_user = await user_service.create_user(db, payload)
        audit_details = payload.model_dump(
            exclude={"password"},
            mode="json",
        )
        audit_details["password_set"] = True
        await audit_service.safe_record(
            db=db,
            action="user.created",
            actor_user_id=current_admin.id,
            resource_type="user",
            resource_id=created_user.id,
            details=audit_details,
        )
        return created_user
    except DuplicateEmailError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


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
        updated_user = await user_service.update_user(db, user_id, payload)
        audit_details = payload.model_dump(
            exclude_unset=True,
            exclude={"password"},
            mode="json",
        )
        if payload.password is not None:
            audit_details["password_changed"] = True
        await audit_service.safe_record(
            db=db,
            action="user.updated",
            actor_user_id=current_admin.id,
            resource_type="user",
            resource_id=user_id,
            details=audit_details,
        )
        return updated_user
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DuplicateEmailError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except CannotRemoveLastAdminError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.patch(
    "/{user_id}/soft-delete",
    response_model=UserAdminResponse,
    summary="Soft-delete one user as admin",
)
async def soft_delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> UserAdminResponse:
    """Deactivate a user without removing the database row."""

    try:
        user = await user_service.soft_delete_user(db, user_id, current_admin.id)
        await audit_service.safe_record(
            db=db,
            action="user.soft_deleted",
            actor_user_id=current_admin.id,
            resource_type="user",
            resource_id=user_id,
        )
        return user
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except CannotDeleteSelfError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except CannotRemoveLastAdminError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.patch(
    "/{user_id}/restore",
    response_model=UserAdminResponse,
    summary="Restore one soft-deleted user as admin",
)
async def restore_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> UserAdminResponse:
    """Reactivate a user account that was previously soft-deleted."""

    try:
        user = await user_service.restore_user(db, user_id)
        await audit_service.safe_record(
            db=db,
            action="user.restored",
            actor_user_id=current_admin.id,
            resource_type="user",
            resource_id=user_id,
        )
        return user
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


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
        await audit_service.safe_record(
            db=db,
            action="user.deleted",
            actor_user_id=current_admin.id,
            resource_type="user",
            resource_id=user_id,
        )
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except CannotDeleteSelfError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except CannotRemoveLastAdminError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
