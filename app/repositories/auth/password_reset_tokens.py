from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import PasswordResetToken


class PasswordResetTokenRepository:
    """SQLAlchemy queries for password reset token persistence."""

    async def create_token(
        self,
        db: AsyncSession,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> PasswordResetToken:
        """Create one password reset token row."""

        token = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        db.add(token)
        await db.commit()
        return token

    async def get_active_by_hash(
        self,
        db: AsyncSession,
        token_hash: str,
    ) -> PasswordResetToken | None:
        """Return a reset token only if it is unused and not expired."""

        query = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.is_used.is_(False),
            PasswordResetToken.expires_at > datetime.now(UTC),
        )
        return await db.scalar(query)

    async def revoke_active_for_user(self, db: AsyncSession, user_id: UUID) -> None:
        """Mark a user's old reset tokens as used before issuing a new one."""

        now = datetime.now(UTC)
        await db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.is_used.is_(False),
            )
            .values(is_used=True, used_at=now)
        )
        await db.commit()

    async def mark_used(self, db: AsyncSession, token: PasswordResetToken) -> None:
        """Consume one reset token so it cannot be reused."""

        token.is_used = True
        token.used_at = datetime.now(UTC)
        await db.commit()

    async def delete_old_tokens(
        self,
        db: AsyncSession,
        older_than: datetime,
    ) -> int:
        """Delete used or expired reset tokens after the retention window passes."""

        result = await db.execute(
            delete(PasswordResetToken).where(
                PasswordResetToken.created_at < older_than,
                or_(
                    PasswordResetToken.is_used.is_(True),
                    PasswordResetToken.expires_at < datetime.now(UTC),
                ),
            )
        )
        await db.commit()
        return result.rowcount or 0


password_reset_token_repository = PasswordResetTokenRepository()
