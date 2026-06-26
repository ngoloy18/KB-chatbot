from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import Form
from pydantic import BaseModel, ConfigDict, Field

from app.constants.permissions import (
    DOCUMENT_PERMISSION_OWNER,
    DOCUMENT_PERMISSION_READ,
    DOCUMENT_PERMISSION_WRITE,
)
from app.core.config import DocumentCategory
from app.models.database import Document


class DocumentPermissionValue(StrEnum):
    """Allowed document permission values admins can assign."""

    READ = DOCUMENT_PERMISSION_READ
    WRITE = DOCUMENT_PERMISSION_WRITE
    OWNER = DOCUMENT_PERMISSION_OWNER


class DocumentCreate(BaseModel):
    """Request body used after upload data has been converted into text."""

    # Field constraints become runtime validation and OpenAPI docs.
    name: str = Field(..., min_length=1, max_length=120)
    # Category must be one of the six allowed values from DocumentCategory.
    category: DocumentCategory
    # Uploaded files are decoded to UTF-8 text before reaching the service.
    content: str = Field(..., min_length=1)
    # These fields are filled by the route from UploadFile metadata.
    file_name: str | None = None
    file_path: str | None = None
    file_type: str | None = None
    content_checksum: str | None = None


class DocumentUploadRequest(BaseModel):
    """Text form fields sent together with the uploaded document file."""

    # These are sent as multipart form fields, not JSON, because a file is included.
    name: str = Field(..., min_length=1, max_length=120)
    category: DocumentCategory

    @classmethod
    def as_form(
        cls,
        name: Annotated[str, Form(..., min_length=1, max_length=120)],
        category: Annotated[DocumentCategory, Form(...)],
    ) -> "DocumentUploadRequest":
        """Tell FastAPI how to build this model from multipart form fields."""

        # FastAPI calls this dependency and passes the submitted form values here.
        return cls(name=name, category=category)


class DocumentUpdate(BaseModel):
    """Request body for partial updates; omitted fields stay unchanged."""

    # All fields are optional because PUT uploads a replacement file plus metadata.
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: DocumentCategory | None = None
    content: str | None = Field(default=None, min_length=1)
    file_name: str | None = None
    file_path: str | None = None
    file_type: str | None = None
    content_checksum: str | None = None


class DocumentResponse(BaseModel):
    """Document shape returned by the API."""

    # from_attributes allows this schema to also serialize object-like records
    # such as SQLAlchemy ORM models if needed later.
    model_config = ConfigDict(from_attributes=True)

    # UUID comes from PostgreSQL and is safe to expose in public API URLs.
    id: UUID
    name: str
    category: DocumentCategory
    # File metadata helps prove file_name/file_path/file_type were saved.
    file_name: str | None = None
    file_path: str | None = None
    file_type: str | None = None
    content_checksum: str | None = None
    content: str
    is_deleted: bool = False
    deleted_at: datetime | None = None
    created_at: datetime


class DocumentListResponse(BaseModel):
    """Paginated response returned by the list endpoint."""

    # items contains only the current page of documents.
    items: list[DocumentResponse]
    # total is the number of matching documents before pagination.
    total: int
    page: int
    page_size: int


class DocumentChunkSearchResult(BaseModel):
    """One matching document chunk returned by search."""

    document_id: UUID
    document_name: str
    category: DocumentCategory
    chunk_id: UUID
    chunk_index: int
    content: str
    token_count: int | None = None


class DocumentChunkSearchResponse(BaseModel):
    """Paginated response for document chunk search."""

    items: list[DocumentChunkSearchResult]
    total: int
    page: int
    page_size: int
    query: str


def document_to_response(document: Document) -> DocumentResponse:
    """Convert a SQLAlchemy Document model into the public API schema."""

    return DocumentResponse(
        id=document.id,
        name=document.title,
        category=DocumentCategory(document.category.name),
        file_name=document.file_name,
        file_path=document.file_path,
        file_type=document.file_type,
        content_checksum=document.content_checksum,
        content=document.content,
        is_deleted=document.is_deleted,
        deleted_at=document.deleted_at,
        created_at=document.created_at,
    )


class DocumentVersionResponse(BaseModel):
    """One immutable document version snapshot."""

    id: UUID
    document_id: UUID
    version_number: int
    name: str
    category: DocumentCategory
    file_name: str | None = None
    file_path: str | None = None
    file_type: str | None = None
    content_checksum: str | None = None
    content: str
    created_at: datetime


class DocumentVersionListResponse(BaseModel):
    """Version history for one document."""

    items: list[DocumentVersionResponse]
    total: int


class DocumentPermissionUpsertRequest(BaseModel):
    """Admin request body for granting or changing document access."""

    user_id: UUID
    permission: DocumentPermissionValue


class DocumentPermissionResponse(BaseModel):
    """Permission row returned by admin document-permission endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    user_id: UUID
    permission: DocumentPermissionValue
    created_at: datetime
    updated_at: datetime
