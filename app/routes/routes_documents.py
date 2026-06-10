# This file defines the API routes for managing documents in the KB chatbot application.
# It uses FastAPI to create endpoints for listing, retrieving, creating, updating, and deleting
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

router = APIRouter(prefix="/documents", tags=["documents"])


# List documents, optionally filtered by name or category
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
    return await document_service.list_documents(name, category, page, page_size)


# Get one document by id
@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get one document",
    description="Return one document by id.",
)
async def get_document(document_id: int) -> DocumentResponse:
    try:
        return await document_service.get_document(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# Create a document from an uploaded text file
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
    file_bytes = await file.read()
    try:
        content = file_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only UTF-8 text files are supported for now.",
        ) from exc

    payload = DocumentCreate(
        name=request.name,
        category=request.category,
        content=content,
    )
    return await document_service.create_document(payload)


# Update a document by id, with partial update support (only fields provided in the request body will be updated)
@router.put(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Update a document",
    description="Update only the fields provided in the request body.",
)
async def update_document(
    document_id: int, payload: DocumentUpdate
) -> DocumentResponse:
    try:
        return await document_service.update_document(document_id, payload)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# Delete a document by id
@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
    description="Delete one document by id.",
)
async def delete_document(document_id: int) -> Response:
    try:
        await document_service.delete_document(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
