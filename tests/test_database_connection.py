import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import DocumentCategory, settings
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
    if not settings.database_url:
        raise AssertionError("DATABASE_URL is missing. Add it to your .env file.")

    async with engine.connect() as connection:
        ping = await connection.scalar(text("SELECT 1"))
        if ping != 1:
            raise AssertionError("Database ping failed.")

        database_name = await connection.scalar(text("SELECT current_database()"))

        schema_exists = await connection.scalar(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.schemata
                    WHERE schema_name = 'kb'
                )
                """
            )
        )
        if not schema_exists:
            raise AssertionError("Schema 'kb' does not exist.")

        table_rows = await connection.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'kb'
                """
            )
        )
        actual_tables = {row.table_name for row in table_rows}
        missing_tables = EXPECTED_TABLES - actual_tables
        if missing_tables:
            raise AssertionError(
                f"Missing table(s) in schema 'kb': {sorted(missing_tables)}"
            )

        category_rows = await connection.execute(
            text("SELECT name FROM kb.document_categories")
        )
        actual_categories = {row.name for row in category_rows}
        expected_categories = {category.value for category in DocumentCategory}
        missing_categories = expected_categories - actual_categories
        if missing_categories:
            raise AssertionError(
                "Missing document categor(y/ies): "
                f"{sorted(missing_categories)}"
            )

    print(f"Database connection OK: connected to '{database_name}'.")
    print("Schema OK: found kb schema and all 9 expected tables.")
    print("Categories OK: found all 6 document categories.")


if __name__ == "__main__":
    try:
        asyncio.run(check_database_connection())
    except Exception as exc:
        print("Database connection test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
