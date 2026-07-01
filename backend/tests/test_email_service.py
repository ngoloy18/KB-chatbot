import asyncio
import sys
from pathlib import Path

# Add the project root to Python's import path when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.services.auth.email import email_service


async def check_email_service_config() -> None:
    """Verify email service handles disabled and incomplete SMTP config safely."""

    original_email_enabled = settings.email_enabled
    original_smtp_host = settings.smtp_host

    try:
        settings.email_enabled = False
        await email_service._send_email(
            "user@example.com",
            "Subject",
            "Body",
        )

        settings.email_enabled = True
        settings.smtp_host = ""
        try:
            email_service._validate_smtp_settings()
        except RuntimeError:
            pass
        else:
            raise AssertionError("Missing SMTP settings should fail when email is enabled.")
    finally:
        settings.email_enabled = original_email_enabled
        settings.smtp_host = original_smtp_host

    print("Email service config OK.")


if __name__ == "__main__":
    try:
        asyncio.run(check_email_service_config())
    except Exception as exc:
        print("Email service config test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
