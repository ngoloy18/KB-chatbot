from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
import logging
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID, uuid4

from app.constants.auth import USER_ROLE_ADMIN
from app.constants.documents import (
    DEFAULT_UPLOAD_CONTENT_TYPE,
    DEFAULT_UPLOAD_FILE_NAME,
)
from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.config import DocumentCategory, settings
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.database import User
from app.schemas.documents.schemas import (
    DocumentCreate,
    DocumentChunkSearchResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadRequest,
    DocumentUpdate,
    DocumentVersionListResponse,
)
from app.services import document_service
from app.services.ai import AIProviderConfigurationError, AIProviderError
from app.services.audit import audit_service
from app.services.documents.exceptions import (
    DocumentAccessDeniedError,
    DocumentCategoryNotFoundError,
    DocumentDuplicateError,
    DocumentNotFoundError,
)

# All document endpoints share the same prefix and Swagger tag.
router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)

# Uploaded files are saved locally here, while metadata is saved in PostgreSQL.
UPLOAD_DIR = Path(settings.upload_dir)


def save_uploaded_file(file: UploadFile, file_bytes: bytes) -> tuple[str, str, str]:
    """Save the uploaded file and return name, path, and content type metadata."""

    # Path(...).name strips any folder parts so clients cannot control our path.
    original_name = Path(file.filename or DEFAULT_UPLOAD_FILE_NAME).name

    # Prefix with a UUID so two uploads with the same filename do not overwrite.
    stored_name = f"{uuid4()}_{original_name}"

    # Create uploads/ the first time a file is uploaded.
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Save the exact uploaded bytes so file_path points to a real local file.
    file_path = UPLOAD_DIR / stored_name
    file_path.write_bytes(file_bytes)

    # Return metadata that will be saved into kb.documents.
    return original_name, file_path.as_posix(), file.content_type or DEFAULT_UPLOAD_CONTENT_TYPE


def cleanup_saved_upload(file_path: str | None) -> None:
    """Remove a saved upload when database work fails or a file is replaced."""

    try:
        if file_path is None:
            return
        saved_path = Path(file_path)
        upload_root = UPLOAD_DIR.resolve()
        resolved_path = saved_path.resolve()
        # Only delete files from the configured upload folder.
        if resolved_path.is_relative_to(upload_root):
            resolved_path.unlink(missing_ok=True)
    except Exception:
        try:
            logger.exception("event=document.upload_cleanup_failed path=%s", file_path)
        except Exception:
            # Cleanup is best-effort and must not replace the request outcome.
            pass


def validate_document_upload(file: UploadFile, file_bytes: bytes) -> None:
    """Validate document upload file rules."""

    original_name = Path(file.filename or "").name
    extension = Path(original_name).suffix.lower()
    if extension not in settings.allowed_upload_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only these file types are allowed: {sorted(settings.allowed_upload_extensions)}.",
        )
    if len(file_bytes) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size must be {settings.max_upload_size_mb}MB or smaller.",
        )


async def build_document_payload_from_upload(
    request: DocumentUploadRequest,
    file: UploadFile,
    require_markdown: bool = False,
) -> DocumentCreate:
    """Read an upload, validate it, save it, and build a create payload."""

    # UploadFile exposes async reads, which keeps this route compatible with
    # FastAPI's async request handling.
    file_bytes = await file.read()
    if require_markdown:
        validate_document_upload(file, file_bytes)

    try:
        # Store document content as text; non-UTF-8 files are rejected clearly.
        content = file_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only UTF-8 text files are supported.",
        ) from exc

    # Store the original file and capture metadata for file_name/file_path/file_type.
    file_name, file_path, file_type = save_uploaded_file(file, file_bytes)
    return DocumentCreate(
        name=request.name,
        category=request.category,
        content=content,
        file_name=file_name,
        file_path=file_path,
        file_type=file_type,
    )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents",
    description="Return paginated documents, optionally filtered by name or category.",
)
async def list_documents(
    name: str | None = Query(
        default=None,
        min_length=1,
        max_length=120,
        description="Filter documents by name.",
    ),
    category: DocumentCategory | None = Query(
        default=None,
        description="Filter documents by one of the six supported KB standards.",
    ),
    page: int = Query(
        default=DEFAULT_PAGE,
        ge=1,
        description="Page number to return. Starts at 1.",
    ),
    page_size: int = Query(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description="Number of documents per page.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentListResponse:
    """List documents with optional filters and pagination.

    Query validation lives in the endpoint signature so FastAPI can reject bad
    requests before they reach the service layer.
    """

    # The route does not build SQL. It passes validated inputs to the service.
    return await document_service.list_documents(
        db=db,
        name=name,
        category=category,
        page=page,
        page_size=page_size,
        current_user_id=current_user.id,
        is_admin=current_user.role == USER_ROLE_ADMIN,
    )


@router.get(
    "/search",
    response_model=DocumentChunkSearchResponse,
    summary="Search document chunks",
    description="Search text chunks from documents the current user can access.",
)
async def search_document_chunks(
    q: str = Query(
        ...,
        min_length=2,
        max_length=200,
        description="Text to search inside document chunks.",
    ),
    category: DocumentCategory | None = Query(
        default=None,
        description="Optional document category filter.",
    ),
    page: int = Query(
        default=DEFAULT_PAGE,
        ge=1,
        description="Page number to return. Starts at 1.",
    ),
    page_size: int = Query(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description="Number of chunk matches per page.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentChunkSearchResponse:
    """Search document chunks after auth and permission filtering."""

    return await document_service.search_document_chunks(
        db=db,
        query=q,
        category=category,
        page=page,
        page_size=page_size,
        current_user_id=current_user.id,
        is_admin=current_user.role == USER_ROLE_ADMIN,
    )


@router.get(
    "/{document_id}/versions",
    response_model=DocumentVersionListResponse,
    summary="List document versions",
    description="Return immutable version snapshots for one document.",
)
async def list_document_versions(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentVersionListResponse:
    """Return version history for one readable document."""

    try:
        return await document_service.list_document_versions(
            db=db,
            document_id=document_id,
            current_user_id=current_user.id,
            is_admin=current_user.role == USER_ROLE_ADMIN,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DocumentAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get one document",
    description="Return one document by id.",
)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    """Return one document by id, translating service errors to HTTP errors."""

    try:
        # The service returns a Pydantic response object if the row exists.
        return await document_service.get_document(
            db=db,
            document_id=document_id,
            current_user_id=current_user.id,
            is_admin=current_user.role == USER_ROLE_ADMIN,
        )
    except DocumentNotFoundError as exc:
        # Keep the service free of FastAPI-specific exceptions.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DocumentAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a markdown document",
    description=(
        "Authenticated upload endpoint that accepts .md files up to 10MB. "
        "Normal-user uploads are private; admin uploads are readable by every user."
    ),
)
async def upload_document(
    request: DocumentUploadRequest = Depends(DocumentUploadRequest.as_form),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    """Create a validated upload with access based on the uploader's role."""

    payload = await build_document_payload_from_upload(
        request=request,
        file=file,
        require_markdown=True,
    )
    try:
        document = await document_service.create_document(
            db=db,
            payload=payload,
            current_user_id=current_user.id,
            is_admin=current_user.role == USER_ROLE_ADMIN,
        )
    except DocumentCategoryNotFoundError as exc:
        cleanup_saved_upload(payload.file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except DocumentDuplicateError as exc:
        cleanup_saved_upload(payload.file_path)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except AIProviderConfigurationError as exc:
        cleanup_saved_upload(payload.file_path)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except AIProviderError as exc:
        cleanup_saved_upload(payload.file_path)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception:
        cleanup_saved_upload(payload.file_path)
        raise

    # The service has committed at this point. Post-commit logging failures must
    # never remove the upload that the document row now references.
    logger.info(
        "event=document.upload_created document_id=%s user_id=%s",
        document.id,
        current_user.id,
    )
    await audit_service.safe_record(
        db=db,
        action="document.upload_created",
        actor_user_id=current_user.id,
        resource_type="document",
        resource_id=document.id,
        details={
            "name": document.name,
            "category": document.category.value,
            "file_name": document.file_name,
        },
    )
    return document


@router.put(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Update a document",
    description="Replace an existing document with a new uploaded text file.",
)
async def update_document(
    document_id: UUID,
    request: DocumentUploadRequest = Depends(DocumentUploadRequest.as_form),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    """Replace a document's file content while keeping its id and created_at."""

    # Reuse the update schema so the service can replace fields while preserving
    # server-owned data such as id and created_at.
    create_payload = await build_document_payload_from_upload(
        request=request,
        file=file,
        require_markdown=True,
    )
    payload = DocumentUpdate(
        name=create_payload.name,
        category=create_payload.category,
        content=create_payload.content,
        file_name=create_payload.file_name,
        file_path=create_payload.file_path,
        file_type=create_payload.file_type,
        content_checksum=create_payload.content_checksum,
    )

    new_file_path = payload.file_path
    old_file_path = None
    try:
        old_file_path = await document_service.get_document_file_path_for_replacement(
            db=db,
            document_id=document_id,
            current_user_id=current_user.id,
            is_admin=current_user.role == USER_ROLE_ADMIN,
        )
        # The service updates only the existing row matching document_id.
        updated_document = await document_service.update_document(
            db=db,
            document_id=document_id,
            payload=payload,
            current_user_id=current_user.id,
            is_admin=current_user.role == USER_ROLE_ADMIN,
        )
    except DocumentNotFoundError as exc:
        cleanup_saved_upload(new_file_path)
        # Route layer decides the HTTP status code for not-found service errors.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DocumentAccessDeniedError as exc:
        cleanup_saved_upload(new_file_path)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except DocumentCategoryNotFoundError as exc:
        cleanup_saved_upload(new_file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except DocumentDuplicateError as exc:
        cleanup_saved_upload(new_file_path)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except AIProviderConfigurationError as exc:
        cleanup_saved_upload(new_file_path)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except AIProviderError as exc:
        cleanup_saved_upload(new_file_path)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception:
        cleanup_saved_upload(new_file_path)
        raise

    # update_document committed and released the replacement lock. The old file
    # can now be removed without risking cleanup of the persisted replacement.
    cleanup_saved_upload(old_file_path)
    logger.info(
        "event=document.upload_replaced document_id=%s user_id=%s",
        updated_document.id,
        current_user.id,
    )
    await audit_service.safe_record(
        db=db,
        action="document.upload_replaced",
        actor_user_id=current_user.id,
        resource_type="document",
        resource_id=updated_document.id,
        details={
            "name": updated_document.name,
            "category": updated_document.category.value,
            "file_name": updated_document.file_name,
        },
    )
    return updated_document


@router.patch(
    "/{document_id}/restore",
    response_model=DocumentResponse,
    summary="Restore a soft-deleted document",
    description="Restore one soft-deleted document by id.",
)
async def restore_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    """Restore a soft-deleted document after permission checks."""

    try:
        restored_document = await document_service.restore_document(
            db=db,
            document_id=document_id,
            current_user_id=current_user.id,
            is_admin=current_user.role == USER_ROLE_ADMIN,
        )
        logger.info(
            "event=document.restored document_id=%s user_id=%s",
            restored_document.id,
            current_user.id,
        )
        await audit_service.safe_record(
            db=db,
            action="document.restored",
            actor_user_id=current_user.id,
            resource_type="document",
            resource_id=restored_document.id,
            details={
                "name": restored_document.name,
                "category": restored_document.category.value,
            },
        )
        return restored_document
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DocumentAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except DocumentDuplicateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a document",
    description="Soft-delete one document by id.",
)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Soft-delete a document and return an empty 204 response."""

    try:
        await document_service.delete_document(
            db=db,
            document_id=document_id,
            current_user_id=current_user.id,
            is_admin=current_user.role == USER_ROLE_ADMIN,
        )
        logger.info(
            "event=document.soft_deleted document_id=%s user_id=%s",
            document_id,
            current_user.id,
        )
        await audit_service.safe_record(
            db=db,
            action="document.soft_deleted",
            actor_user_id=current_user.id,
            resource_type="document",
            resource_id=document_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DocumentAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
