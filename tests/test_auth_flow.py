import asyncio
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete

# Add the project root to Python's import path when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.constants.constants_auth import TOKEN_TYPE_BEARER, USER_ROLE_USER
from app.db.session import AsyncSessionLocal
from app.models.models_database import User
from app.schemas.schemas_auth import LoginRequest, RegisterRequest, VerifyEmailRequest
from app.services.exceptions_auth import EmailNotVerifiedError
from app.services.services_auth import auth_service


async def check_normal_user_auth_flow() -> None:
    """Verify a normal user can register and login."""

    email = f"test_user_{uuid4().hex[:8]}@example.com"
    password = "password123"

    async with AsyncSessionLocal() as db:
        try:
            registered_user = await auth_service.register_user(
                db,
                RegisterRequest(
                    email=email,
                    password=password,
                    full_name="Test User",
                ),
            )
            if registered_user.user.role != USER_ROLE_USER:
                raise AssertionError("Registered users should have role='user'.")

            try:
                await auth_service.login(
                    db,
                    LoginRequest(email=email, password=password),
                )
            except EmailNotVerifiedError:
                pass
            else:
                raise AssertionError("Unverified users should not be able to login.")

            await auth_service.verify_email(
                db,
                VerifyEmailRequest(token=registered_user.verification_token),
            )

            token = await auth_service.login(
                db,
                LoginRequest(email=email, password=password),
            )
            if token.token_type != TOKEN_TYPE_BEARER or not token.access_token:
                raise AssertionError("Login did not return a Bearer access token.")
        finally:
            # Keep the real local database clean after this test creates a user.
            await db.execute(delete(User).where(User.email == email))
            await db.commit()

    print("Normal user register/login flow OK.")


if __name__ == "__main__":
    try:
        asyncio.run(check_normal_user_auth_flow())
    except Exception as exc:
        print("Normal user auth flow FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
