from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.auth import USER_ROLE_USER
from app.models.database import Document, User


class UserRepository:
    """SQLAlchemy queries for user persistence."""

    async def get_by_email(self, db: AsyncSession, email: str) -> User | None:
        """Return one user by email if it exists."""

        # db.scalar returns the first selected User object or None.
        query = select(User).where(User.email == email)
        return await db.scalar(query)

    async def get_by_id(self, db: AsyncSession, user_id: UUID) -> User | None:
        """Return one user by id if it exists."""

        query = select(User).where(User.id == user_id)
        return await db.scalar(query)

    async def get_by_password_reset_token_hash(
        self,
        db: AsyncSession,
        token_hash: str,
    ) -> User | None:
        """Return one user by password reset token hash if it exists."""

        query = select(User).where(User.password_reset_token_hash == token_hash)
        return await db.scalar(query)

    async def list_users(
        self,
        db: AsyncSession,
        page: int,
        page_size: int,
    ) -> tuple[list[User], int]:
        """Return one page of users and the total user count."""

        offset = (page - 1) * page_size
        total = await db.scalar(select(func.count()).select_from(User))
        query = select(User).order_by(User.created_at.desc()).offset(offset).limit(page_size)
        rows = await db.scalars(query)
        return list(rows), total or 0

    async def create_user(
        self,
        db: AsyncSession,
        email: str,
        hashed_password: str,
        full_name: str | None = None,
        role: str = USER_ROLE_USER,
        is_email_verified: bool = False,
    ) -> User:
        """Create one user row."""

        # Repository owns ORM object creation so services do not depend on table details.
        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
            is_active=True,
            is_email_verified=is_email_verified,
        )
        db.add(user)
        # commit writes the INSERT to PostgreSQL.
        await db.commit()
        return user

    async def delete_user(self, db: AsyncSession, user: User) -> None:
        """Delete one user row."""

        # Keep documents but remove ownership so the users foreign key will not block.
        await db.execute(
            update(Document)
            .where(Document.created_by == user.id)
            .values(created_by=None)
        )
        await db.delete(user)
        await db.commit()


user_repository = UserRepository()
