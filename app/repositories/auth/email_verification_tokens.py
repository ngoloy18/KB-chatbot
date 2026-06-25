from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import EmailVerificationToken


class EmailVerificationTokenRepository:
    """SQLAlchemy queries for email verification token persistence."""

    async def create_token(
        self,
        db: AsyncSession,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> EmailVerificationToken:
        """Create one email verification token row."""

        token = EmailVerificationToken(
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
    ) -> EmailVerificationToken | None:
        """Return a token only if it is unused and not expired."""

        query = select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.is_used.is_(False),
            EmailVerificationToken.expires_at > datetime.now(UTC),
        )
        return await db.scalar(query)

    async def revoke_active_for_user(self, db: AsyncSession, user_id: UUID) -> None:
        """Mark a user's old verification tokens as used before issuing a new one."""

        now = datetime.now(UTC)
        await db.execute(
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user_id,
                EmailVerificationToken.is_used.is_(False),
            )
            .values(is_used=True, used_at=now)
        )
        await db.commit()

    async def mark_used(
        self,
        db: AsyncSession,
        token: EmailVerificationToken,
    ) -> None:
        """Consume one token so it cannot be reused."""

        token.is_used = True
        token.used_at = datetime.now(UTC)
        await db.commit()


email_verification_token_repository = EmailVerificationTokenRepository()
