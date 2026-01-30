"""
Custom exceptions for Riot API clients.

Provides a hierarchy of domain-specific exceptions that are decoupled from
HTTP/FastAPI concerns. Translation to HTTP responses happens at the router layer.
"""

from typing import Optional, Self

from fastapi.openapi.utils import status_code_ranges


class RiotAPIError(Exception):
    """
    Base exception for all Riot API errors.

    Attributes:
        message: Human-readable error description.
        status_code: Optional HTTP status code from the API response.
    """

    def __init__(self: Self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class RiotAPIAuthenticationError(RiotAPIError):
    """
    Raised when API key is invalid, expired, or lacks permissions.

    Triggered by 401 Unauthorized or 403 Forbidden responses.
    """

    def __init__(self: Self, message: str = "Invalid or expired API key"):
        super().__init__(message, status_code=401)


class RiotAPINotFoundError(RiotAPIError):
    """
    Raised when the requested resource does not exist.

    Triggered by 404 Not Found responses (e.g., summoner doesn't exist).
    """

    def __init__(self: Self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class RiotAPIRateLimitError(RiotAPIError):
    """
    Raised when rate limit is exceeded after all retry attempts.

    Triggered by 429 Too Many Requests responses.

    Attributes:
        retry_after: Seconds to wait before retrying (from Retry-After header).
    """

    def __init__(
        self: Self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None
    ):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class RiotAPIServerError(RiotAPIError):
    """
    Raised for server-side errors from the Riot API.

    Triggered by 5xx responses after retry attempts are exhausted.
    """

    def __init__(
        self: Self,
        message: str = "Server error",
        status_code: int = 500
    ):
        super().__init__(message, status_code=status_code)


class RiotAPIValidationError(RiotAPIError):
    """
    Raised for client-side validation errors before making API requests.

    Examples: invalid PUUID format, empty player name, invalid region code.
    """

    def __init__(self: Self, message: str):
        super().__init__(message, status_code=400)


class RiotAPITimeoutError(RiotAPIError):
    """
    Raised when a request times out.

    Indicates the API did not respond within the configured timeout period.
    """

    def __init__(self: Self, message: str = "Request timed out"):
        super().__init__(message, status_code=504)
