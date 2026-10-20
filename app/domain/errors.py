"""Failures expressed in application language rather than HTTP or SQL."""


class ApplicationError(Exception):
    """A rejected application operation."""


class InvalidOperation(ApplicationError):
    """The requested operation violates a business rule."""


class NotFound(ApplicationError):
    """A requested entity does not exist or is not accessible."""


class Forbidden(ApplicationError):
    """The current role cannot perform this operation."""


class Unauthenticated(ApplicationError):
    """Credentials are missing or invalid."""


class DuplicateUser(InvalidOperation):
    """A user with the same email already exists."""
