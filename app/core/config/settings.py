from enum import StrEnum
import os

from dotenv import load_dotenv


load_dotenv()


class DocumentCategory(StrEnum):
    """Allowed knowledge-base document categories.

    StrEnum makes each enum member behave like a string, so FastAPI/Pydantic can
    validate incoming values and show the allowed choices in Swagger.
    """

    CODING_CONVENTION = "coding-convention"
    GIT_FLOW = "git-flow"
    PULL_REQUEST = "pull-request"
    DATABASE = "database"
    API_STANDARD = "api-standard"
    LOGGING = "logging"


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self) -> None:
        # App metadata is used by Swagger docs and the health endpoint.
        self.app_name = os.getenv("APP_NAME", "developer-kb-chatbot")
        self.app_title = os.getenv("APP_TITLE", "Developer KB Chatbot API")
        self.app_version = os.getenv("APP_VERSION", "0.2.0")
        self.app_description = os.getenv(
            "APP_DESCRIPTION",
            "FastAPI with SQLAlchemy, JWT auth, and protected uploads.",
        )

        # AI provider settings keep model/provider choices outside application code.
        self.ai_provider = os.getenv("AI_PROVIDER", "").strip().lower()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini_model = os.getenv("GEMINI_MODEL", "").strip()
        self.chat_history_limit = int(os.getenv("CHAT_HISTORY_LIMIT", "12"))
        self.embeddings_enabled = (
            os.getenv("EMBEDDINGS_ENABLED", "false").lower() == "true"
        )
        self.embedding_provider = (
            os.getenv("EMBEDDING_PROVIDER", self.ai_provider).strip().lower()
        )
        self.gemini_embedding_model = os.getenv("GEMINI_EMBEDDING_MODEL", "").strip()
        self.rag_top_k = int(os.getenv("RAG_TOP_K", "5"))
        self.rag_max_context_tokens = int(os.getenv("RAG_MAX_CONTEXT_TOKENS", "1800"))
        self.rag_min_similarity = float(os.getenv("RAG_MIN_SIMILARITY", "0"))

        # Database settings keep local, Docker, and production values out of code.
        self.database_url = os.getenv("DATABASE_URL", "")
        self.database_echo = os.getenv("DATABASE_ECHO", "false").lower() == "true"
        self.database_schema = os.getenv("DATABASE_SCHEMA", "kb")

        # Auth settings control token signing and the first seeded admin account.
        self.jwt_secret = os.getenv("JWT_SECRET", "")
        self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
        )
        self.refresh_token_expire_minutes = int(
            os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "10080")
        )
        self.password_reset_token_expire_minutes = int(
            os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "30")
        )
        self.password_reset_token_retention_days = int(
            os.getenv("PASSWORD_RESET_TOKEN_RETENTION_DAYS", "7")
        )
        self.email_verification_token_expire_minutes = int(
            os.getenv("EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES", "1440")
        )
        self.email_verification_token_retention_days = int(
            os.getenv("EMAIL_VERIFICATION_TOKEN_RETENTION_DAYS", "7")
        )
        self.initial_admin_email = os.getenv("INITIAL_ADMIN_EMAIL", "")
        self.initial_admin_password = os.getenv("INITIAL_ADMIN_PASSWORD", "")

        # Email settings are used for verification and password reset messages.
        self.email_enabled = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
        self.email_return_dev_tokens = (
            os.getenv("EMAIL_RETURN_DEV_TOKENS", "true").lower() == "true"
        )
        self.smtp_host = os.getenv("SMTP_HOST", "")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from_email = os.getenv("SMTP_FROM_EMAIL", self.smtp_username)
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        self.frontend_verify_email_url = os.getenv(
            "FRONTEND_VERIFY_EMAIL_URL",
            "http://127.0.0.1:8000/docs",
        )
        self.frontend_reset_password_url = os.getenv(
            "FRONTEND_RESET_PASSWORD_URL",
            "http://127.0.0.1:8000/docs",
        )

        # Upload settings make file storage rules configurable per environment.
        self.upload_dir = os.getenv("UPLOAD_DIR", "uploads")
        self.max_upload_size_mb = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
        self.max_upload_size_bytes = self.max_upload_size_mb * 1024 * 1024
        self.allowed_upload_extensions = self._parse_upload_extensions(
            os.getenv("ALLOWED_UPLOAD_EXTENSIONS", ".md")
        )

        # Rate limit settings protect the API from repeated requests by one client.
        self.rate_limit_enabled = (
            os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
        )
        self.rate_limit_requests = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
        self.rate_limit_window_seconds = int(
            os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")
        )
        self.rate_limit_excluded_paths = self._parse_csv_values(
            os.getenv("RATE_LIMIT_EXCLUDED_PATHS", "/docs,/openapi.json,/redoc")
        )
        self.sensitive_rate_limit_requests = int(
            os.getenv("SENSITIVE_RATE_LIMIT_REQUESTS", "5")
        )
        self.sensitive_rate_limit_window_seconds = int(
            os.getenv("SENSITIVE_RATE_LIMIT_WINDOW_SECONDS", "60")
        )
        self.sensitive_rate_limit_paths = self._parse_csv_values(
            os.getenv(
                "SENSITIVE_RATE_LIMIT_PATHS",
                (
                    "/api/auth/login,"
                    "/api/auth/register,"
                    "/api/auth/forgot-password,"
                    "/api/auth/reset-password,"
                    "/api/auth/resend-verification,"
                    "/api/documents/upload"
                ),
            )
        )

    @staticmethod
    def _parse_upload_extensions(raw_value: str) -> set[str]:
        """Convert comma-separated extensions from .env into normalized values."""

        extensions = {
            value.strip().lower()
            for value in raw_value.split(",")
            if value.strip()
        }
        return {
            extension if extension.startswith(".") else f".{extension}"
            for extension in extensions
        }

    @staticmethod
    def _parse_csv_values(raw_value: str) -> set[str]:
        """Convert comma-separated setting values into a clean set."""

        return {
            value.strip()
            for value in raw_value.split(",")
            if value.strip()
        }


settings = Settings()
