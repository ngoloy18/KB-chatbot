"""Compatibility exports for all SQLAlchemy model classes.

The actual models are split into focused files so each table is easier to read.
Importing this module still loads every model, which keeps older imports and
Alembic metadata discovery working.
"""

from app.constants.constants_database import SCHEMA_NAME
from app.models.models_document_categories import DocumentCategoryModel
from app.models.models_users import User
from app.models.models_documents import Document
from app.models.models_document_chunks import DocumentChunk
from app.models.models_document_permissions import DocumentPermission
from app.models.models_chat_sessions import ChatSession
from app.models.models_chat_messages import ChatMessage
from app.models.models_message_sources import MessageSource
from app.models.models_ai_runs import AIRun
from app.models.models_refresh_tokens import RefreshToken

__all__ = [
    "AIRun",
    "ChatMessage",
    "ChatSession",
    "Document",
    "DocumentCategoryModel",
    "DocumentChunk",
    "DocumentPermission",
    "MessageSource",
    "RefreshToken",
    "SCHEMA_NAME",
    "User",
]
