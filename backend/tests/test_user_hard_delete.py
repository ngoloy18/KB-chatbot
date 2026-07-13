import asyncio
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.constants.ai import AI_RUN_STATUS_SUCCESS
from app.constants.auth import USER_ROLE_USER
from app.constants.chat import CHAT_ROLE_ASSISTANT, CHAT_ROLE_USER
from app.constants.documents import DOCUMENT_STATUS_READY
from app.constants.permissions import DOCUMENT_PERMISSION_READ
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.database import (
    AIRun,
    AuditLog,
    ChatMessage,
    ChatSession,
    Document,
    DocumentCategoryModel,
    DocumentPermission,
    User,
)
from app.repositories.users.users import user_repository
from app.services.users.service import user_service


async def check_user_hard_delete_with_related_rows() -> None:
    """Hard delete should clean owned rows and keep shared history safe."""

    email = f"hard_delete_{uuid4().hex[:8]}@example.com"
    admin_id = uuid4()

    async with AsyncSessionLocal() as db:
        user_id = None
        document_id = None
        try:
            user = await user_repository.create_user(
                db=db,
                email=email,
                hashed_password=hash_password("Password123!"),
                role=USER_ROLE_USER,
                is_email_verified=True,
            )
            user_id = user.id

            category = await db.scalar(
                select(DocumentCategoryModel).where(
                    DocumentCategoryModel.name == "api-standard"
                )
            )
            if category is None:
                raise AssertionError("api-standard category should exist.")

            document = Document(
                title=f"Hard Delete Owner {uuid4().hex[:8]}",
                category_id=category.id,
                file_name="hard-delete.md",
                file_type="text/markdown",
                content="# Hard delete\n\nOwned by a user being deleted.",
                status=DOCUMENT_STATUS_READY,
                created_by=user.id,
            )
            db.add(document)
            await db.commit()
            await db.refresh(document)
            document_id = document.id

            db.add(
                DocumentPermission(
                    document_id=document.id,
                    user_id=user.id,
                    permission=DOCUMENT_PERMISSION_READ,
                )
            )
            session = ChatSession(user_id=user.id, title="Hard delete chat")
            db.add(session)
            await db.commit()
            await db.refresh(session)

            user_message = ChatMessage(
                session_id=session.id,
                role=CHAT_ROLE_USER,
                content="Question",
            )
            assistant_message = ChatMessage(
                session_id=session.id,
                role=CHAT_ROLE_ASSISTANT,
                content="Answer",
            )
            db.add_all([user_message, assistant_message])
            await db.commit()
            await db.refresh(user_message)
            await db.refresh(assistant_message)

            db.add(
                AIRun(
                    session_id=session.id,
                    user_message_id=user_message.id,
                    assistant_message_id=assistant_message.id,
                    model_name="test-model",
                    status=AI_RUN_STATUS_SUCCESS,
                )
            )
            db.add(
                AuditLog(
                    actor_user_id=user.id,
                    action="test.user_action",
                    resource_type="user",
                    resource_id=user.id,
                    details={"source": "test_user_hard_delete"},
                )
            )
            await db.commit()

            await user_service.delete_user(
                db=db,
                user_id=user.id,
                current_admin_id=admin_id,
            )

            deleted_user = await user_repository.get_by_id(db, user.id)
            if deleted_user is not None:
                raise AssertionError("Hard-deleted user row should be removed.")

            kept_document = await db.scalar(
                select(Document).where(Document.id == document.id)
            )
            if kept_document is None:
                raise AssertionError("Hard delete should not delete documents.")
            if kept_document.created_by is not None:
                raise AssertionError("Hard delete should clear document created_by.")
            if kept_document.is_global_read:
                raise AssertionError(
                    "Hard delete must not publish a normal user's private document."
                )

            remaining_session = await db.scalar(
                select(ChatSession).where(ChatSession.id == session.id)
            )
            if remaining_session is not None:
                raise AssertionError("Hard delete should remove user chat sessions.")
        finally:
            await db.rollback()
            if document_id is not None:
                await db.execute(
                    delete(DocumentPermission).where(
                        DocumentPermission.document_id == document_id
                    )
                )
                await db.execute(delete(Document).where(Document.id == document_id))
            if user_id is not None:
                await db.execute(delete(User).where(User.id == user_id))
            await db.commit()

    print("User hard delete OK.")


if __name__ == "__main__":
    try:
        asyncio.run(check_user_hard_delete_with_related_rows())
    except Exception as exc:
        print("User hard delete test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
