"""Unit tests for riot_exception_to_http."""

import pytest
from fastapi import HTTPException

from app.internal.riot_api.http_errors import riot_exception_to_http
from app.internal.riot_api.exceptions import (
    RiotAPINotFoundError,
    RiotAPIValidationError,
    RiotAPIAuthenticationError,
    RiotAPIRateLimitError,
    RiotAPITimeoutError,
    RiotAPIServerError,
    RiotAPIError,
)


@pytest.mark.parametrize(
    "exc_class,expected_status",
    [
        (RiotAPINotFoundError, 404),
        (RiotAPIValidationError("invalid input"), 400),
        (RiotAPIAuthenticationError(), 503),
        (RiotAPIRateLimitError(), 503),
        (RiotAPITimeoutError(), 504),
        (RiotAPIServerError(), 502),
    ],
)
def test_riot_exception_to_http_maps_to_correct_status(exc_class, expected_status):
    exc = exc_class() if not isinstance(exc_class, RiotAPIError) else exc_class
    result = riot_exception_to_http(exc)
    assert isinstance(result, HTTPException)
    assert result.status_code == expected_status


def test_riot_exception_to_http_validation_error_detail():
    exc = RiotAPIValidationError("Invalid PUUID format")
    result = riot_exception_to_http(exc)
    assert result.status_code == 400
    assert result.detail == "Invalid PUUID format"


def test_riot_exception_to_http_rate_limit_retry_after():
    exc = RiotAPIRateLimitError(retry_after=60)
    result = riot_exception_to_http(exc)
    assert result.status_code == 503
    assert result.headers["Retry-After"] == "60"


def test_riot_exception_to_http_base_error_falls_to_500():
    exc = RiotAPIError("unknown error")
    result = riot_exception_to_http(exc)
    assert result.status_code == 500
    assert result.detail == "Internal server error"
