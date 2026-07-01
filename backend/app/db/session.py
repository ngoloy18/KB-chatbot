from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


# The async engine owns the connection pool and knows how to talk to PostgreSQL.
engine = create_async_engine(settings.database_url, echo=settings.database_echo)

# AsyncSessionLocal is a factory that creates database sessions for requests.
# expire_on_commit=False keeps ORM objects readable after commit() finishes.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield one async database session per request."""

    # FastAPI opens the session before the route runs and closes it afterward.
    async with AsyncSessionLocal() as session:
        yield session
