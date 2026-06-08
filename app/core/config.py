from enum import StrEnum


class DocumentCategory(StrEnum):
    CODING_CONVENTION = "coding-convention"
    GIT_FLOW = "git-flow"
    PULL_REQUEST = "pull-request"
    DATABASE = "database"
    API_STANDARD = "api-standard"
    LOGGING = "logging"
