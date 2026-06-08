from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import DocumentCategory


class DocumentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    category: DocumentCategory
    content: str = Field(..., min_length=1)


class DocumentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: DocumentCategory | None = None
    content: str | None = Field(default=None, min_length=1)


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: DocumentCategory
    content: str
    created_at: datetime
