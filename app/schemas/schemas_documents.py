from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Form
from pydantic import BaseModel, ConfigDict, Field
from app.core.config import DocumentCategory
from app.models.models_database import Document


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
    content: str
    created_at: datetime


class DocumentListResponse(BaseModel):
    """Paginated response returned by the list endpoint."""

    # items contains only the current page of documents.
    items: list[DocumentResponse]
    # total is the number of matching documents before pagination.
    total: int
    page: int
    page_size: int


def document_to_response(document: Document) -> DocumentResponse:
    """Convert a SQLAlchemy Document model into the public API schema."""

    return DocumentResponse(
        id=document.id,
        name=document.title,
        category=DocumentCategory(document.category.name),
        file_name=document.file_name,
        file_path=document.file_path,
        file_type=document.file_type,
        content=document.content,
        created_at=document.created_at,
    )
