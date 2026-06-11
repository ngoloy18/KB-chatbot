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
from app.core.config import DocumentCategory
from app.schemas.schemas_documents import (
    DocumentCreate,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadRequest,
    DocumentUpdate,
)
from app.services.services_documents import DocumentNotFoundError, document_service

# All document endpoints share the same prefix and Swagger tag.
router = APIRouter(prefix="/documents", tags=["documents"])


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
) -> DocumentListResponse:
    """List documents with optional filters and pagination.

    Query validation lives in the endpoint signature so FastAPI can reject bad
    requests before they reach the service layer.
    """

    return await document_service.list_documents(name, category, page, page_size)


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get one document",
    description="Return one document by id.",
)
async def get_document(document_id: int) -> DocumentResponse:
    """Return one document by id, translating service errors to HTTP errors."""

    try:
        return await document_service.get_document(document_id)
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

    # Convert form data plus file content into the same create schema used by
    # the service, so the service does not need to understand file uploads.
    payload = DocumentCreate(
        name=request.name,
        category=request.category,
        content=content,
    )
    return await document_service.create_document(payload)


@router.put(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Update a document",
    description="Replace an existing document with a new uploaded text file.",
)
async def update_document(
    document_id: int,
    request: DocumentUploadRequest = Depends(DocumentUploadRequest.as_form),
    file: UploadFile = File(...),
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

    # Reuse the update schema so the service can replace fields while preserving
    # server-owned data such as id and created_at.
    payload = DocumentUpdate(
        name=request.name,
        category=request.category,
        content=content,
    )

    try:
        return await document_service.update_document(document_id, payload)
    except DocumentNotFoundError as exc:
        # Route layer decides the HTTP status code for not-found service errors.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
    description="Delete one document by id.",
)
async def delete_document(document_id: int) -> Response:
    """Delete a document and return an empty 204 response."""

    try:
        await document_service.delete_document(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
