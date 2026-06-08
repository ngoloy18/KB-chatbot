from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.config import DocumentCategory
from app.schemas.documents import DocumentCreate, DocumentResponse, DocumentUpdate
from app.services.documents import DocumentNotFoundError, document_service


router = APIRouter(prefix="/documents", tags=["documents"])


@router.get(
    "",
    response_model=list[DocumentResponse],
    summary="List documents",
    description="Return all documents, optionally filtered by category.",
)
async def list_documents(
    category: DocumentCategory | None = Query(
        default=None,
        description="Filter documents by one of the six supported KB standards.",
    )
) -> list[DocumentResponse]:
    return await document_service.list_documents(category)


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


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a document",
    description="Create a document and generate its id and creation timestamp.",
)
async def create_document(payload: DocumentCreate) -> DocumentResponse:
    return await document_service.create_document(payload)


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
