"""Shared constants used by SQLAlchemy model files."""

# All application-owned tables live in the PostgreSQL schema named "kb".
# Keeping the schema name in one constant prevents typo bugs in table mappings.
SCHEMA_NAME = "kb"
