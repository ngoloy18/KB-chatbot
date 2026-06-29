from typing import Any
from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import AuditLog


logger = logging.getLogger(__name__)


class AuditService:
    """Persistence helper for append-only audit events."""

    async def record(
        self,
        db: AsyncSession,
        action: str,
        actor_user_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Write one audit event and commit it immediately."""

        audit_log = AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )
        db.add(audit_log)
        await db.commit()
        await db.refresh(audit_log)
        return audit_log

    async def safe_record(
        self,
        db: AsyncSession,
        action: str,
        actor_user_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Write audit data without breaking the user-facing action if logging fails."""

        try:
            await self.record(
                db=db,
                action=action,
                actor_user_id=actor_user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
            )
        except Exception:
            await db.rollback()
            logger.exception(
                "event=audit.write_failed action=%s resource_type=%s resource_id=%s",
                action,
                resource_type,
                resource_id,
            )


audit_service = AuditService()
