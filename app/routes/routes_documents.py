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
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID, uuid4

from app.core.config import DocumentCategory, settings
from app.db.session import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.models_database import User
from app.schemas.schemas_documents import (
    DocumentCreate,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadRequest,
    DocumentUpdate,
)
from app.services import document_service
from app.services.exceptions_documents import (
    DocumentAccessDeniedError,
    DocumentCategoryNotFoundError,
    DocumentNotFoundError,
)

# All document endpoints share the same prefix and Swagger tag.
router = APIRouter(prefix="/documents", tags=["documents"])

# Uploaded files are saved locally here, while metadata is saved in PostgreSQL.
UPLOAD_DIR = Path(settings.upload_dir)


def save_uploaded_file(file: UploadFile, file_bytes: bytes) -> tuple[str, str, str]:
    """Save the uploaded file and return name, path, and content type metadata."""

    # Path(...).name strips any folder parts so clients cannot control our path.
    original_name = Path(file.filename or "uploaded-document.txt").name

    # Prefix with a UUID so two uploads with the same filename do not overwrite.
    stored_name = f"{uuid4()}_{original_name}"

    # Create uploads/ the first time a file is uploaded.
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Save the exact uploaded bytes so file_path points to a real local file.
    file_path = UPLOAD_DIR / stored_name
    file_path.write_bytes(file_bytes)

    # Return metadata that will be saved into kb.documents.
    return original_name, file_path.as_posix(), file.content_type or "text/plain"


def validate_admin_upload(file: UploadFile, file_bytes: bytes) -> None:
    """Validate Week 3 admin upload file rules."""

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
        validate_admin_upload(file, file_bytes)

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
        default=1,
        ge=1,
        description="Page number to return. Starts at 1.",
    ),
    page_size: int = Query(
        default=10,
        ge=1,
        le=100,
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
        is_admin=current_user.role == "admin",
    )


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
            is_admin=current_user.role == "admin",
        )
    except DocumentNotFoundError as exc:
        # Keep the service free of FastAPI-specific exceptions.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DocumentAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document file and create a document",
    description="Create a document from a text file uploaded through a multipart form.",
)
async def upload_document(
    request: DocumentUploadRequest = Depends(DocumentUploadRequest.as_form),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> DocumentResponse:
    """Create a document from a validated admin markdown upload."""

    payload = await build_document_payload_from_upload(
        request=request,
        file=file,
        require_markdown=True,
    )
    try:
        # The service creates the PostgreSQL row inside kb.documents.
        return await document_service.create_document(db, payload)
    except DocumentCategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a markdown document as admin",
    description="Admin-only upload endpoint that accepts .md files up to 10MB.",
)
async def upload_document_as_admin(
    request: DocumentUploadRequest = Depends(DocumentUploadRequest.as_form),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> DocumentResponse:
    """Create a document from a validated admin markdown upload."""

    payload = await build_document_payload_from_upload(
        request=request,
        file=file,
        require_markdown=True,
    )
    try:
        return await document_service.create_document(db, payload)
    except DocumentCategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


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
    )

    try:
        # The service updates only the existing row matching document_id.
        return await document_service.update_document(
            db=db,
            document_id=document_id,
            payload=payload,
            current_user_id=current_user.id,
            is_admin=current_user.role == "admin",
        )
    except DocumentNotFoundError as exc:
        # Route layer decides the HTTP status code for not-found service errors.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DocumentAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except DocumentCategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
    description="Delete one document by id.",
)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete a document and return an empty 204 response."""

    try:
        # The service checks existence before deleting so missing IDs return 404.
        await document_service.delete_document(
            db=db,
            document_id=document_id,
            current_user_id=current_user.id,
            is_admin=current_user.role == "admin",
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DocumentAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
