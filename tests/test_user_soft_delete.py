import asyncio
from datetime import UTC, datetime, timedelta
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, select

# Add the project root to Python's import path when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.constants.auth import USER_ROLE_USER
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.database import EmailVerificationToken, RefreshToken, User
from app.repositories.auth.email_verification_tokens import (
    email_verification_token_repository,
)
from app.repositories.auth.refresh_tokens import refresh_token_repository
from app.repositories.users.users import user_repository
from app.services.users.service import user_service


async def check_user_soft_delete() -> None:
    """Verify soft delete deactivates a user without removing the row."""

    email = f"soft_delete_{uuid4().hex[:8]}@example.com"

    async with AsyncSessionLocal() as db:
        try:
            user = await user_repository.create_user(
                db=db,
                email=email,
                hashed_password=hash_password("Password123!"),
                role=USER_ROLE_USER,
                is_email_verified=True,
            )
            await refresh_token_repository.create_token(
                db=db,
                user_id=user.id,
                token_hash=f"{uuid4().hex}{uuid4().hex}",
                token_id=uuid4().hex,
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
            await email_verification_token_repository.create_token(
                db=db,
                user_id=user.id,
                token_hash=f"{uuid4().hex}{uuid4().hex}",
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )

            response = await user_service.soft_delete_user(
                db=db,
                user_id=user.id,
                current_admin_id=uuid4(),
            )
            if response.is_active:
                raise AssertionError("Soft-deleted user should be inactive.")

            saved_user = await user_repository.get_by_id(db, user.id)
            if saved_user is None:
                raise AssertionError("Soft delete should keep the user row.")
            if saved_user.is_active:
                raise AssertionError("User row should be marked inactive.")

            active_refresh_token = await db.scalar(
                select(RefreshToken).where(
                    RefreshToken.user_id == user.id,
                    RefreshToken.is_revoked.is_(False),
                )
            )
            if active_refresh_token is not None:
                raise AssertionError("Soft delete should revoke refresh tokens.")

            active_verification_token = await db.scalar(
                select(EmailVerificationToken).where(
                    EmailVerificationToken.user_id == user.id,
                    EmailVerificationToken.is_used.is_(False),
                )
            )
            if active_verification_token is not None:
                raise AssertionError("Soft delete should revoke verification tokens.")
        finally:
            await db.execute(delete(User).where(User.email == email))
            await db.commit()

    print("User soft delete OK.")


if __name__ == "__main__":
    try:
        asyncio.run(check_user_soft_delete())
    except Exception as exc:
        print("User soft delete test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
