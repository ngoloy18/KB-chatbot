from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import require_admin
from app.models.database import User
from app.schemas.documents.schemas import (
    DocumentPermissionResponse,
    DocumentPermissionUpsertRequest,
)
from app.services import document_service
from app.services.audit import audit_service
from app.services.documents.exceptions import (
    DocumentAccessConflictError,
    DocumentNotFoundError,
    DocumentPermissionNotFoundError,
)
from app.services.users.exceptions import UserNotFoundError


# Keep admin document-access endpoints separate from normal document CRUD.
router = APIRouter(prefix="/documents", tags=["document-permissions"])


@router.get(
    "/{document_id}/permissions",
    response_model=list[DocumentPermissionResponse],
    summary="List document permissions as admin",
)
async def list_document_permissions(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> list[DocumentPermissionResponse]:
    """Return all user access rules for one document."""

    try:
        return await document_service.list_document_permissions(db, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put(
    "/{document_id}/permissions",
    response_model=DocumentPermissionResponse,
    summary="Grant document permission as admin",
)
async def grant_document_permission(
    document_id: UUID,
    payload: DocumentPermissionUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> DocumentPermissionResponse:
    """Grant or update one user's access to one document."""

    try:
        permission = await document_service.grant_document_permission(
            db,
            document_id,
            payload,
        )
        await audit_service.safe_record(
            db=db,
            action="document.permission_granted",
            actor_user_id=current_admin.id,
            resource_type="document",
            resource_id=document_id,
            details={
                "target_user_id": str(payload.user_id),
                "permission": permission.permission.value,
            },
        )
        return permission
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DocumentAccessConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.delete(
    "/{document_id}/permissions/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke document permission as admin",
)
async def revoke_document_permission(
    document_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> Response:
    """Remove one user's access to one document."""

    try:
        await document_service.revoke_document_permission(db, document_id, user_id)
        await audit_service.safe_record(
            db=db,
            action="document.permission_revoked",
            actor_user_id=current_admin.id,
            resource_type="document",
            resource_id=document_id,
            details={"target_user_id": str(user_id)},
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DocumentPermissionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
