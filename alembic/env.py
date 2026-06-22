import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import settings
from app.db.base import Base
from app.models import models_database


# Alembic gives this file a config object based on alembic.ini.
config = context.config

# The real database URL lives in .env, so we copy it into Alembic at runtime.
config.set_main_option("sqlalchemy.url", settings.database_url)

# Configure terminal logging using the [loggers] section from alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic compares this metadata against the database during autogenerate.
target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    """Limit Alembic autogenerate to the app schema instead of all schemas."""

    if type_ == "schema":
        return name in [None, models_database.SCHEMA_NAME]
    return True


def run_migrations_offline() -> None:
    """Create SQL text without opening a database connection."""

    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
    )

    with context.begin_transaction():
        # Run every migration needed to reach the requested revision.
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Run Alembic using a normal sync connection inside the async wrapper."""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Open an async PostgreSQL connection for online migrations."""

    configuration = config.get_section(config.config_ini_section, {})

    # async_engine_from_config understands postgresql+asyncpg URLs.
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # Alembic's migration internals are sync, so run_sync bridges the two worlds.
        await connection.run_sync(do_run_migrations)

    # Dispose closes the migration engine cleanly after Alembic is done.
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for normal migrations that connect to PostgreSQL."""

    asyncio.run(run_async_migrations())


# Alembic chooses offline or online mode based on the command being run.
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
