"""Compatibility exports for all SQLAlchemy model classes.

The actual models are split into focused files so each table is easier to read.
Importing this module still loads every model, which keeps older imports and
Alembic metadata discovery working.
"""

from app.constants.database import SCHEMA_NAME
from app.models.documents.categories import DocumentCategoryModel
from app.models.auth.users import User
from app.models.documents.documents import Document
from app.models.documents.chunks import DocumentChunk
from app.models.documents.permissions import DocumentPermission
from app.models.chat.sessions import ChatSession
from app.models.chat.messages import ChatMessage
from app.models.chat.message_sources import MessageSource
from app.models.chat.ai_runs import AIRun
from app.models.auth.email_verification_tokens import EmailVerificationToken
from app.models.auth.refresh_tokens import RefreshToken

__all__ = [
    "AIRun",
    "ChatMessage",
    "ChatSession",
    "Document",
    "DocumentCategoryModel",
    "DocumentChunk",
    "DocumentPermission",
    "EmailVerificationToken",
    "MessageSource",
    "RefreshToken",
    "SCHEMA_NAME",
    "User",
]
