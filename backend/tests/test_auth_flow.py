import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete

# Keep this test local and deterministic even when the developer .env enables SMTP.
os.environ.setdefault("EMAIL_ENABLED", "false")
os.environ.setdefault("EMAIL_RETURN_DEV_TOKENS", "true")

# Add the project root to Python's import path when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.constants.auth import TOKEN_TYPE_BEARER, USER_ROLE_USER
from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import AsyncSessionLocal
from app.models.database import User
from app.schemas.auth.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.services.auth.exceptions import EmailNotVerifiedError
from app.services.auth.exceptions import InvalidCredentialsError
from app.services.auth.exceptions import InvalidPasswordResetTokenError
from app.services.auth.service import auth_service


async def check_normal_user_auth_flow() -> None:
    """Verify a normal user can register and login."""

    email = f"test_user_{uuid4().hex[:8]}@example.com"
    password = "Password123!"
    original_access_token_expire_minutes = settings.access_token_expire_minutes

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

            resent_verification = await auth_service.resend_verification(
                db,
                ResendVerificationRequest(email=email),
            )
            if not resent_verification.verification_token:
                raise AssertionError("Resend verification did not return a token.")

            await auth_service.verify_email(
                db,
                VerifyEmailRequest(token=resent_verification.verification_token),
            )

            token = await auth_service.login(
                db,
                LoginRequest(email=email, password=password),
            )
            if token.token_type != TOKEN_TYPE_BEARER or not token.access_token:
                raise AssertionError("Login did not return a Bearer access token.")
            if not token.refresh_token:
                raise AssertionError("Login did not return a refresh token.")

            settings.access_token_expire_minutes = -1
            expired_pair = await auth_service.login(
                db,
                LoginRequest(email=email, password=password),
            )
            settings.access_token_expire_minutes = original_access_token_expire_minutes
            try:
                decode_access_token(expired_pair.access_token)
            except ValueError:
                pass
            else:
                raise AssertionError("An expired access token should be rejected.")

            refreshed_token = await auth_service.refresh_token(
                db,
                RefreshTokenRequest(refresh_token=expired_pair.refresh_token),
            )
            if refreshed_token.token_type != TOKEN_TYPE_BEARER:
                raise AssertionError("Refresh did not return a Bearer token.")
            if not refreshed_token.access_token:
                raise AssertionError("Refresh did not return a new access token.")
            if not refreshed_token.refresh_token:
                raise AssertionError("Refresh did not rotate the refresh token.")
            decode_access_token(refreshed_token.access_token)

            try:
                await auth_service.refresh_token(
                    db,
                    RefreshTokenRequest(refresh_token=expired_pair.refresh_token),
                )
            except InvalidCredentialsError:
                pass
            else:
                raise AssertionError("A rotated refresh token should be one-time use.")

            await auth_service.logout(
                db,
                RefreshTokenRequest(refresh_token=refreshed_token.refresh_token),
            )
            try:
                await auth_service.refresh_token(
                    db,
                    RefreshTokenRequest(refresh_token=refreshed_token.refresh_token),
                )
            except InvalidCredentialsError:
                pass
            else:
                raise AssertionError("Logged out refresh token should be revoked.")

            reset_response = await auth_service.forgot_password(
                db,
                ForgotPasswordRequest(email=email),
            )
            if not reset_response.reset_token:
                raise AssertionError("Password reset did not return a reset token.")

            new_password = "NewPassword123!"
            await auth_service.reset_password(
                db,
                ResetPasswordRequest(
                    token=reset_response.reset_token,
                    new_password=new_password,
                ),
            )
            try:
                await auth_service.reset_password(
                    db,
                    ResetPasswordRequest(
                        token=reset_response.reset_token,
                        new_password="AnotherPassword123!",
                    ),
                )
            except InvalidPasswordResetTokenError:
                pass
            else:
                raise AssertionError("Password reset token should be one-time use.")

            try:
                await auth_service.login(
                    db,
                    LoginRequest(email=email, password=password),
                )
            except InvalidCredentialsError:
                pass
            else:
                raise AssertionError("Old password should stop working after reset.")

            new_login = await auth_service.login(
                db,
                LoginRequest(email=email, password=new_password),
            )
            if not new_login.access_token or not new_login.refresh_token:
                raise AssertionError("New password login did not return tokens.")
        finally:
            settings.access_token_expire_minutes = original_access_token_expire_minutes
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
