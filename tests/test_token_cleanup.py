import asyncio
from datetime import UTC, datetime, timedelta
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, select

# Add the project root to Python's import path when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.database import EmailVerificationToken, PasswordResetToken, User
from app.repositories.auth.email_verification_tokens import (
    email_verification_token_repository,
)
from app.repositories.auth.password_reset_tokens import password_reset_token_repository
from app.repositories.users.users import user_repository


async def check_token_cleanup() -> None:
    """Verify cleanup deletes only old used/expired auth helper tokens."""

    email = f"token_cleanup_{uuid4().hex[:8]}@example.com"
    now = datetime.now(UTC)
    older_than = now - timedelta(days=7)
    old_time = now - timedelta(days=8)

    async with AsyncSessionLocal() as db:
        try:
            user = await user_repository.create_user(
                db=db,
                email=email,
                hashed_password=hash_password("Password123!"),
                is_email_verified=False,
            )
            old_used_token = EmailVerificationToken(
                user_id=user.id,
                token_hash=f"{uuid4().hex}{uuid4().hex}",
                expires_at=now + timedelta(days=1),
                is_used=True,
                used_at=old_time,
                created_at=old_time,
                updated_at=old_time,
            )
            old_expired_token = EmailVerificationToken(
                user_id=user.id,
                token_hash=f"{uuid4().hex}{uuid4().hex}",
                expires_at=old_time,
                is_used=False,
                created_at=old_time,
                updated_at=old_time,
            )
            active_token = EmailVerificationToken(
                user_id=user.id,
                token_hash=f"{uuid4().hex}{uuid4().hex}",
                expires_at=now + timedelta(days=1),
                is_used=False,
                created_at=old_time,
                updated_at=old_time,
            )
            db.add_all([old_used_token, old_expired_token, active_token])
            old_used_reset_token = PasswordResetToken(
                user_id=user.id,
                token_hash=f"{uuid4().hex}{uuid4().hex}",
                expires_at=now + timedelta(days=1),
                is_used=True,
                used_at=old_time,
                created_at=old_time,
                updated_at=old_time,
            )
            old_expired_reset_token = PasswordResetToken(
                user_id=user.id,
                token_hash=f"{uuid4().hex}{uuid4().hex}",
                expires_at=old_time,
                is_used=False,
                created_at=old_time,
                updated_at=old_time,
            )
            active_reset_token = PasswordResetToken(
                user_id=user.id,
                token_hash=f"{uuid4().hex}{uuid4().hex}",
                expires_at=now + timedelta(days=1),
                is_used=False,
                created_at=old_time,
                updated_at=old_time,
            )
            db.add_all(
                [old_used_reset_token, old_expired_reset_token, active_reset_token]
            )
            await db.commit()

            deleted_count = await email_verification_token_repository.delete_old_tokens(
                db,
                older_than,
            )
            if deleted_count != 2:
                raise AssertionError(f"Expected 2 deleted tokens, got {deleted_count}.")

            remaining_tokens = await db.scalars(
                select(EmailVerificationToken).where(
                    EmailVerificationToken.user_id == user.id
                )
            )
            remaining_hashes = {token.token_hash for token in remaining_tokens}
            if active_token.token_hash not in remaining_hashes:
                raise AssertionError("Cleanup should keep active tokens.")
            if old_used_token.token_hash in remaining_hashes:
                raise AssertionError("Cleanup should delete old used tokens.")
            if old_expired_token.token_hash in remaining_hashes:
                raise AssertionError("Cleanup should delete old expired tokens.")

            deleted_reset_count = (
                await password_reset_token_repository.delete_old_tokens(
                    db,
                    older_than,
                )
            )
            if deleted_reset_count != 2:
                raise AssertionError(
                    f"Expected 2 deleted reset tokens, got {deleted_reset_count}."
                )

            remaining_reset_tokens = await db.scalars(
                select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
            )
            remaining_reset_hashes = {
                token.token_hash for token in remaining_reset_tokens
            }
            if active_reset_token.token_hash not in remaining_reset_hashes:
                raise AssertionError("Cleanup should keep active reset tokens.")
            if old_used_reset_token.token_hash in remaining_reset_hashes:
                raise AssertionError("Cleanup should delete old used reset tokens.")
            if old_expired_reset_token.token_hash in remaining_reset_hashes:
                raise AssertionError("Cleanup should delete old expired reset tokens.")
        finally:
            await db.execute(delete(User).where(User.email == email))
            await db.commit()

    print("Token cleanup OK.")


if __name__ == "__main__":
    try:
        asyncio.run(check_token_cleanup())
    except Exception as exc:
        print("Token cleanup test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
