import asyncio
from datetime import UTC, datetime, timedelta
import sys
from pathlib import Path

# Allow running this script directly from the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.repositories.auth.email_verification_tokens import (
    email_verification_token_repository,
)


async def cleanup_tokens() -> None:
    """Delete old used/expired email verification tokens."""

    # Retention is configurable so local/dev/prod can keep different history.
    older_than = datetime.now(UTC) - timedelta(
        days=settings.email_verification_token_retention_days
    )

    async with AsyncSessionLocal() as db:
        deleted_count = await email_verification_token_repository.delete_old_tokens(
            db,
            older_than,
        )

    print(f"Deleted {deleted_count} old email verification token(s).")


if __name__ == "__main__":
    try:
        asyncio.run(cleanup_tokens())
    except Exception as exc:
        print("Token cleanup failed.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
