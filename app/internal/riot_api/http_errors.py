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
    match exc:
        case RiotAPINotFoundError():
            return HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Summoner not found"
            )

        case RiotAPIValidationError():
            return HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=exc.message
            )

        case RiotAPIAuthenticationError():
            # Don't expose internal auth issues to clients
            return HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable"
            )

        case RiotAPIRateLimitError():
            headers = {}
            if exc.retry_after:
                headers["Retry-After"] = str(exc.retry_after)
            return HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable",
                headers=headers if headers else None
            )

        case RiotAPITimeoutError():
            return HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="External service timeout"
            )

        case RiotAPIServerError():
            return HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="External service error"
            )

        case _:
            return HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )
