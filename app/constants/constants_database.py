"""Database-related constants shared by models, migrations, and tests."""

from app.core.config import settings


# All application-owned tables live in one PostgreSQL schema.
# The default is "kb", but .env can override it for another deployment.
SCHEMA_NAME = settings.database_schema
