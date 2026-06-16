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

from app.core.config import DocumentCategory
from app.db.session import get_db
from app.schemas.schemas_documents import (
    DocumentCreate,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadRequest,
    DocumentUpdate,
)
from app.services.services_documents import (
    DocumentCategoryNotFoundError,
    DocumentNotFoundError,
    document_service,
)

# All document endpoints share the same prefix and Swagger tag.
router = APIRouter(prefix="/documents", tags=["documents"])

# Uploaded files are saved locally here, while metadata is saved in PostgreSQL.
UPLOAD_DIR = Path("uploads")


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
) -> DocumentListResponse:
    """List documents with optional filters and pagination.

    Query validation lives in the endpoint signature so FastAPI can reject bad
    requests before they reach the service layer.
    """

    # The route does not build SQL. It passes validated inputs to the service.
    return await document_service.list_documents(db, name, category, page, page_size)


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get one document",
    description="Return one document by id.",
)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Return one document by id, translating service errors to HTTP errors."""

    try:
        # The service returns a Pydantic response object if the row exists.
        return await document_service.get_document(db, document_id)
    except DocumentNotFoundError as exc:
        # Keep the service free of FastAPI-specific exceptions.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


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
) -> DocumentResponse:
    """Create a document from a UTF-8 text file uploaded as multipart form data."""

    # UploadFile exposes async reads, which keeps this route compatible with
    # FastAPI's async request handling.
    file_bytes = await file.read()
    try:
        # Store document content as text; non-UTF-8 files are rejected clearly.
        content = file_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only UTF-8 text files are supported for now.",
        ) from exc

    # Store the original file and capture metadata for file_name/file_path/file_type.
    file_name, file_path, file_type = save_uploaded_file(file, file_bytes)

    # Convert form data plus file content into the same create schema used by
    # the service, so the service does not need to understand file uploads.
    payload = DocumentCreate(
        name=request.name,
        category=request.category,
        content=content,
        file_name=file_name,
        file_path=file_path,
        file_type=file_type,
    )
    try:
        # The service creates the PostgreSQL row inside kb.documents.
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
) -> DocumentResponse:
    """Replace a document's file content while keeping its id and created_at."""

    # PUT uses multipart form data here because the replacement content comes
    # from a newly uploaded file, not from a JSON request body.
    file_bytes = await file.read()
    try:
        # The service stores plain text content, so uploaded files must be UTF-8.
        content = file_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only UTF-8 text files are supported for now.",
        ) from exc

    # Updating a document also saves the replacement file and updates metadata.
    file_name, file_path, file_type = save_uploaded_file(file, file_bytes)

    # Reuse the update schema so the service can replace fields while preserving
    # server-owned data such as id and created_at.
    payload = DocumentUpdate(
        name=request.name,
        category=request.category,
        content=content,
        file_name=file_name,
        file_path=file_path,
        file_type=file_type,
    )

    try:
        # The service updates only the existing row matching document_id.
        return await document_service.update_document(db, document_id, payload)
    except DocumentNotFoundError as exc:
        # Route layer decides the HTTP status code for not-found service errors.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
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
) -> Response:
    """Delete a document and return an empty 204 response."""

    try:
        # The service checks existence before deleting so missing IDs return 404.
        await document_service.delete_document(db, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
