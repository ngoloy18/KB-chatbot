class UserNotFoundError(ValueError):
    """Raised when an admin targets a user id that does not exist."""


class CannotDeleteSelfError(ValueError):
    """Raised when an admin tries to delete their own account."""
