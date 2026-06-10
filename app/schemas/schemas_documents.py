# This file defines the Pydantic models for the document-related API endpoints, including the request and response schemas.

from datetime import datetime
from typing import Annotated

from fastapi import Form
from pydantic import BaseModel, ConfigDict, Field
from app.core.config import DocumentCategory


# This file defines the Pydantic models for the document-related API endpoints, including the request and response schemas.
class DocumentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    category: DocumentCategory
    content: str = Field(..., min_length=1)


class DocumentUploadRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    category: DocumentCategory

    @classmethod
    def as_form(
        cls,
        name: Annotated[str, Form(..., min_length=1, max_length=120)],
        category: Annotated[DocumentCategory, Form(...)],
    ) -> "DocumentUploadRequest":
        return cls(name=name, category=category)


# The DocumentUpdate model is used for updating documents, and all fields are optional to allow for partial updates.
class DocumentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: DocumentCategory | None = None
    content: str | None = Field(default=None, min_length=1)


# The DocumentResponse model is used for returning document data in API responses, and it includes the document's id, name, category, content, and creation timestamp.
class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: DocumentCategory
    content: str
    created_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int
