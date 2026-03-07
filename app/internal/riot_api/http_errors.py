"""
HTTP error translation for Riot API exceptions.

Converts domain-specific Riot API exceptions to FastAPI HTTPException
responses. This keeps HTTP concerns in the router/controller layer.
"""

from fastapi import HTTPException, status

from .exceptions import (
    RiotAPIError,
    RiotAPIAuthenticationError,
    RiotAPINotFoundError,
    RiotAPIRateLimitError,
    RiotAPIServerError,
    RiotAPIValidationError,
    RiotAPITimeoutError,
)


def riot_exception_to_http(exc: RiotAPIError) -> HTTPException:
    """
    Convert a Riot API exception to an appropriate HTTP exception.

    This function maps domain-specific exceptions to HTTP status codes
    and error messages suitable for API responses.

    Args:
        exc: A RiotAPIError or one of its subclasses.

    Returns:
        HTTPException with appropriate status code and detail message.

    Example:
        try:
            summoner = riot_api.get_summoner(name, tag)
        except RiotAPIError as e:
            raise riot_exception_to_http(e)
    """
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail_msg = "Internal server error"
    headers = None

    if isinstance(exc, RiotAPINotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
        detail_msg = "Summoner not found"
    elif isinstance(exc, RiotAPIValidationError):
        status_code = status.HTTP_400_BAD_REQUEST
        detail_msg = exc.message
    elif isinstance(exc, RiotAPIAuthenticationError):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        detail_msg = "Service temporarily unavailable"
    elif isinstance(exc, RiotAPIRateLimitError):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        detail_msg = "Service temporarily unavailable"
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
    elif isinstance(exc, RiotAPITimeoutError):
        status_code = status.HTTP_504_GATEWAY_TIMEOUT
        detail_msg = "External service timeout"
    elif isinstance(exc, RiotAPIServerError):
        status_code = status.HTTP_502_BAD_GATEWAY
        detail_msg = "External service error"

    return HTTPException(status_code=status_code, detail=detail_msg, headers=headers)
