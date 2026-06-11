from datetime import datetime
from typing import Annotated

from fastapi import Form
from pydantic import BaseModel, ConfigDict, Field
from app.core.config import DocumentCategory


class DocumentCreate(BaseModel):
    """Request body used after upload data has been converted into text."""

    # Field constraints become both runtime validation and OpenAPI docs.
    name: str = Field(..., min_length=1, max_length=120)
    category: DocumentCategory
    content: str = Field(..., min_length=1)


class DocumentUploadRequest(BaseModel):
    """Text form fields sent together with the uploaded document file."""

    name: str = Field(..., min_length=1, max_length=120)
    category: DocumentCategory

    @classmethod
    def as_form(
        cls,
        name: Annotated[str, Form(..., min_length=1, max_length=120)],
        category: Annotated[DocumentCategory, Form(...)],
    ) -> "DocumentUploadRequest":
        """Tell FastAPI how to build this model from multipart form fields."""

        return cls(name=name, category=category)


class DocumentUpdate(BaseModel):
    """Request body for partial updates; omitted fields stay unchanged."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: DocumentCategory | None = None
    content: str | None = Field(default=None, min_length=1)


class DocumentResponse(BaseModel):
    """Document shape returned by the API."""

    # from_attributes allows this schema to also serialize object-like records
    # if the in-memory store is replaced with ORM/database models later.
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: DocumentCategory
    content: str
    created_at: datetime


class DocumentListResponse(BaseModel):
    """Paginated response returned by the list endpoint."""

    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int
