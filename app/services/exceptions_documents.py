class DocumentNotFoundError(ValueError):
    """Raised when a requested document id does not exist."""

    pass


class DocumentCategoryNotFoundError(ValueError):
    """Raised when the configured category rows are missing from the database."""

    pass


class DocumentAccessDeniedError(ValueError):
    """Raised when a normal user is not allowed to read a document."""

    pass


class DocumentPermissionNotFoundError(ValueError):
    """Raised when a document permission row does not exist."""

    pass
