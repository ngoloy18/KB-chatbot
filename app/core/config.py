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
        self.database_url = os.getenv("DATABASE_URL", "")
        self.database_echo = os.getenv("DATABASE_ECHO", "false").lower() == "true"


settings = Settings()
