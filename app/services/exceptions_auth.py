class DuplicateEmailError(ValueError):
    """Raised when registering with an email that already exists."""

    pass


class InvalidCredentialsError(ValueError):
    """Raised when login credentials are incorrect."""

    pass


class InactiveUserError(ValueError):
    """Raised when an inactive user tries to authenticate."""

    pass
