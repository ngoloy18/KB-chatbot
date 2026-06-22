from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models_database import User


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

    async def create_user(
        self,
        db: AsyncSession,
        email: str,
        hashed_password: str,
        full_name: str | None = None,
        role: str = "user",
    ) -> User:
        """Create one user row."""

        # Repository owns ORM object creation so services do not depend on table details.
        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
            is_active=True,
        )
        db.add(user)
        # commit writes the INSERT to PostgreSQL.
        await db.commit()
        return user


user_repository = UserRepository()
