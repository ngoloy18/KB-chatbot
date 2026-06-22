class DocumentNotFoundError(ValueError):
    """Raised when a requested document id does not exist."""

    pass


class DocumentCategoryNotFoundError(ValueError):
    """Raised when the configured category rows are missing from the database."""

    pass
