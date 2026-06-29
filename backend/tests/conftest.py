import os
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Return the database URL CI/pytest should use for isolated tests."""

    database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("Set TEST_DATABASE_URL or DATABASE_URL before running tests.")
    return database_url


@pytest.fixture
async def test_db_session(test_database_url: str) -> AsyncGenerator[AsyncSession, None]:
    """Yield one rollback-safe async DB session for pytest-based tests."""

    engine = create_async_engine(test_database_url, echo=False)
    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
    await engine.dispose()
