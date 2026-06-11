from enum import StrEnum


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
