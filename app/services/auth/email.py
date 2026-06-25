import asyncio
from email.message import EmailMessage
import smtplib

from app.core.config import settings


class EmailService:
    """Send application emails through SMTP."""

    async def send_verification_email(self, recipient_email: str, token: str) -> None:
        """Send the email verification token to a new user."""

        verify_url = self._build_token_url(settings.frontend_verify_email_url, token)
        subject = "Verify your KB Chatbot account"
        body = (
            "Welcome to KB Chatbot.\n\n"
            "Use this token to verify your email:\n"
            f"{token}\n\n"
            "Verification link:\n"
            f"{verify_url}\n"
        )
        await self._send_email(recipient_email, subject, body)

    async def send_password_reset_email(self, recipient_email: str, token: str) -> None:
        """Send the password reset token to a user."""

        reset_url = self._build_token_url(settings.frontend_reset_password_url, token)
        subject = "Reset your KB Chatbot password"
        body = (
            "A password reset was requested for your KB Chatbot account.\n\n"
            "Use this token to reset your password:\n"
            f"{token}\n\n"
            "Reset link:\n"
            f"{reset_url}\n\n"
            "If you did not request this, you can ignore this email.\n"
        )
        await self._send_email(recipient_email, subject, body)

    async def _send_email(
        self,
        recipient_email: str,
        subject: str,
        body: str,
    ) -> None:
        """Send one email without blocking the async route handler."""

        if not settings.email_enabled:
            return

        await asyncio.to_thread(
            self._send_email_sync,
            recipient_email,
            subject,
            body,
        )

    def _send_email_sync(
        self,
        recipient_email: str,
        subject: str,
        body: str,
    ) -> None:
        """Use smtplib to send one plain-text email."""

        self._validate_smtp_settings()

        message = EmailMessage()
        message["From"] = settings.smtp_from_email
        message["To"] = recipient_email
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)

    @staticmethod
    def _build_token_url(base_url: str, token: str) -> str:
        """Append token as a query parameter to the configured frontend URL."""

        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}token={token}"

    @staticmethod
    def _validate_smtp_settings() -> None:
        """Fail fast if email sending is enabled but SMTP config is incomplete."""

        required_values = {
            "SMTP_HOST": settings.smtp_host,
            "SMTP_USERNAME": settings.smtp_username,
            "SMTP_PASSWORD": settings.smtp_password,
            "SMTP_FROM_EMAIL": settings.smtp_from_email,
        }
        missing_values = [
            name
            for name, value in required_values.items()
            if not value
        ]
        if missing_values:
            raise RuntimeError(
                "Email sending is enabled but missing setting(s): "
                + ", ".join(missing_values)
            )


email_service = EmailService()
