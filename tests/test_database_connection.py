import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

# Add the project root to Python's import path when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import DocumentCategory, settings
from app.constants.constants_database import SCHEMA_NAME
from app.db.session import engine


EXPECTED_TABLES = {
    "ai_runs",
    "chat_messages",
    "chat_sessions",
    "document_categories",
    "document_chunks",
    "document_permissions",
    "documents",
    "message_sources",
    "users",
}


async def check_database_connection() -> None:
    """Verify the real local database has the schema the app expects."""

    # Without DATABASE_URL, SQLAlchemy does not know where PostgreSQL is.
    if not settings.database_url:
        raise AssertionError("DATABASE_URL is missing. Add it to your .env file.")

    # Opening a connection proves host, port, username, password, and DB name work.
    async with engine.connect() as connection:
        # SELECT 1 is a tiny query used as a database ping.
        ping = await connection.scalar(text("SELECT 1"))
        if ping != 1:
            raise AssertionError("Database ping failed.")

        # Report the actual database name so wrong .env values are obvious.
        database_name = await connection.scalar(text("SELECT current_database()"))

        # Check that the custom schema exists before checking tables inside it.
        schema_exists = await connection.scalar(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.schemata
                    WHERE schema_name = :schema_name
                )
                """
            ),
            {"schema_name": SCHEMA_NAME},
        )
        if not schema_exists:
            raise AssertionError(f"Schema '{SCHEMA_NAME}' does not exist.")

        # Read actual table names from PostgreSQL metadata.
        table_rows = await connection.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = :schema_name
                """
            ),
            {"schema_name": SCHEMA_NAME},
        )
        actual_tables = {row.table_name for row in table_rows}

        # If any expected table is missing, the app may fail at runtime.
        missing_tables = EXPECTED_TABLES - actual_tables
        if missing_tables:
            raise AssertionError(
                f"Missing table(s) in schema '{SCHEMA_NAME}': {sorted(missing_tables)}"
            )

        # The document API depends on these seed category rows.
        category_rows = await connection.execute(
            text(f"SELECT name FROM {SCHEMA_NAME}.document_categories")
        )
        actual_categories = {row.name for row in category_rows}
        expected_categories = {category.value for category in DocumentCategory}

        # Missing categories mean POST /api/documents cannot map category to category_id.
        missing_categories = expected_categories - actual_categories
        if missing_categories:
            raise AssertionError(
                "Missing document categor(y/ies): "
                f"{sorted(missing_categories)}"
            )

    print(f"Database connection OK: connected to '{database_name}'.")
    print(f"Schema OK: found {SCHEMA_NAME} schema and all 9 expected tables.")
    print("Categories OK: found all 6 document categories.")


if __name__ == "__main__":
    try:
        # asyncio.run starts the event loop needed by async SQLAlchemy.
        asyncio.run(check_database_connection())
    except Exception as exc:
        # Print a short human-friendly failure before returning a non-zero exit code.
        print("Database connection test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
