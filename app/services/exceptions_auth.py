class DuplicateEmailError(ValueError):
    """Raised when registering with an email that already exists."""

    pass


class InvalidCredentialsError(ValueError):
    """Raised when login credentials are incorrect."""

    pass


class InactiveUserError(ValueError):
    """Raised when an inactive user tries to authenticate."""


class EmailNotVerifiedError(ValueError):
    """Raised when a user tries to login before verifying their email."""


class InvalidVerificationTokenError(ValueError):
    """Raised when an email verification token is missing or invalid."""

    pass
