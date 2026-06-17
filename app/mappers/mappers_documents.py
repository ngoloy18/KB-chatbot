from app.core.config import DocumentCategory
from app.models.models_database import Document
from app.schemas.schemas_documents import DocumentResponse


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
