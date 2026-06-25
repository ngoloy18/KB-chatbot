from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import RefreshToken


class RefreshTokenRepository:
    """SQLAlchemy queries for refresh token sessions."""

    async def create_token(
        self,
        db: AsyncSession,
        user_id: UUID,
        token_hash: str,
        token_id: str,
        expires_at: datetime,
    ) -> RefreshToken:
        """Create one refresh token row for a login session."""

        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            token_id=token_id,
            expires_at=expires_at,
        )
        db.add(refresh_token)
        await db.commit()
        return refresh_token

    async def get_active_by_hash(
        self,
        db: AsyncSession,
        token_hash: str,
    ) -> RefreshToken | None:
        """Return a refresh token only if it has not expired or been revoked."""

        query = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked.is_(False),
            RefreshToken.expires_at > datetime.now(UTC),
        )
        return await db.scalar(query)

    async def revoke_token(self, db: AsyncSession, refresh_token: RefreshToken) -> None:
        """Mark one refresh token as revoked so it cannot be used again."""

        refresh_token.is_revoked = True
        refresh_token.revoked_at = datetime.now(UTC)
        await db.commit()

    async def revoke_all_for_user(self, db: AsyncSession, user_id: UUID) -> None:
        """Revoke every active refresh token for one user."""

        now = datetime.now(UTC)
        await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked.is_(False),
            )
            .values(is_revoked=True, revoked_at=now)
        )
        await db.commit()


refresh_token_repository = RefreshTokenRepository()
