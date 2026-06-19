import asyncio
import sys
from pathlib import Path

# Allow running this script directly from the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.repositories.repositories_users import user_repository


async def seed_admin() -> None:
    """Create the first admin user if it does not already exist."""

    if not settings.initial_admin_email or not settings.initial_admin_password:
        raise RuntimeError(
            "INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD must be set in .env."
        )

    async with AsyncSessionLocal() as db:
        existing_user = await user_repository.get_by_email(
            db,
            settings.initial_admin_email,
        )
        if existing_user is not None:
            if existing_user.role == "admin":
                print("Admin already exists; no changes made.")
                return
            existing_user.role = "admin"
            await db.commit()
            print("Existing user promoted to admin.")
            return

        await user_repository.create_user(
            db=db,
            email=settings.initial_admin_email,
            hashed_password=hash_password(settings.initial_admin_password),
            role="admin",
        )
        print("Admin user created.")


if __name__ == "__main__":
    try:
        asyncio.run(seed_admin())
    except Exception as exc:
        print("Admin seed failed.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
