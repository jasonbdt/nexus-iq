"""
Base HTTP client for Riot API.

Provides common HTTP functionality, error handling, and retry logic
for all domain-specific clients.
"""

from abc import ABC
from typing import Self, Type, TypeVar, Union

import os

import aiohttp
from aiohttp import ClientRequest, ClientHandlerType, ClientResponse, ClientTimeout, ClientSession
from aiohttp.client_exceptions import ContentTypeError
from pydantic import BaseModel

from .config import RiotAPIConfig, RiotRegion, RiotPlatform, REGION_TO_PLATFORM
from .exceptions import (
    RiotAPIError,
    RiotAPIAuthenticationError,
    RiotAPINotFoundError,
    RiotAPIRateLimitError,
    RiotAPIServerError,
    RiotAPITimeoutError,
    RiotAPIValidationError,
)
from .models import RiotError
from ..session import get_session
from ..logging import get_logger
from ..redis import acquire_riot

T = TypeVar("T", bound=BaseModel)


async def retry_middleware(
    req: ClientRequest,
    handler: ClientHandlerType
) -> ClientResponse:
    """Retry failed HTTP requests up to 3 times, but never retry 429 (rate limit)."""
    for _ in range(3):
        response = await handler(req)
        if response.ok or response.status == 429:
            return response

    return response


class RiotAPIBase(ABC):
    """
    Abstract base class for Riot API clients.

    Provides common HTTP functionality, error handling, and retry logic.
    Subclasses implement domain-specific API methods.

    Args:
        _config: Immutable configuration for API access.
        _logger: Logger instance for this client.
        _session: aiohttp session with retry configuration.
    """

    def __init__(self: Self, config: RiotAPIConfig) -> None:
        self._config = config
        self._logger = get_logger(self.__class__.__name__)
        self._session = get_session()

    def _create_session(self: Self) -> ClientSession:
        headers = {"X-Riot-Token": os.getenv("RIOT_API_KEY")}
        timeout = ClientTimeout(total=self._config.timeout_seconds)

        return aiohttp.ClientSession(
            headers=headers,
            timeout=timeout,
            middlewares=(retry_middleware,)
        )

    def _build_url(
        self: Self,
        routing: Union[RiotRegion, RiotPlatform],
        path: str
    ) -> str:
        """
        Build the full API URL.

        Args:
            routing: Regional or platform routing value.
            path: API endpoint path (without leading slash).

        Returns:
            Complete URL for the API request.
        """
        base = self._config.base_url_template.format(routing=routing.value)
        return f"{base}/{path}"

    async def _request(
        self: Self,
        routing: Union[RiotRegion, RiotPlatform],
        path: str,
        response_model: Union[Type[T], RiotError]
    ) -> T:
        """
        Make an HTTP GET request to the Riot API.

        Args:
            routing: Regional or platform routing value.
            path: API endpoint path.
            response_model: Pydantic model to parse response into

        Returns:
            Parsed response as the specified model type.

        Raises:
            RiotAPIAuthenticationError: If API key is invalid.
            RiotAPINotFoundError: If resource is not found.
            RiotAPIRateLimitError: If rate limit exceeded after retries.
            RiotAPIServerError: For server-side errors.
            RiotAPITimeoutError: If request times out.
            RiotAPIError: For other errors.
        """
        url = self._build_url(routing, path)
        self._logger.debug("Requesting: %s", url)
        await acquire_riot(routing.value)
        try:
            response = await self._session.get(url)
        except aiohttp.client_exceptions.ConnectionTimeoutError as exc:
            self._logger.error("Request timed out: %s", url)
            raise RiotAPITimeoutError(
                f"Request timed out after {self._config.timeout_seconds}s"
            ) from exc

        return await self._handle_response(response, response_model)

    async def _request_list(
        self: Self,
        routing: Union[RiotRegion, RiotPlatform],
        path: str,
        item_model: Type[T],
    ) -> list[T]:
        """
        Make an HTTP GET request expecting a list response.

        Args:
            routing: Regional or platform routing value.
            path: API endpoint path.
            item_model: Pydantic model for list items.

        Returns:
            List of parsed items.

        Raises:
            Same exceptions as _request.
        """
        url = self._build_url(routing, path)
        self._logger.debug("Requesting list: %s", url)

        await acquire_riot(routing.value)
        try:
            response = await self._session.get(url)
        except aiohttp.client_exceptions.ConnectionTimeoutError as exc:
            raise RiotAPITimeoutError(
                f"Request timed out after {self._config.timeout_seconds}s"
            ) from exc

        self._check_response_status(response)

        try:
            data = await response.json()
            return [item_model.model_validate(item) for item in data]
        except (ContentTypeError, ValueError) as exc:
            self._logger.error("Failed to parse response: %s", exc)
            raise RiotAPIError(f"Invalid response format: {exc}") from exc

    async def _request_raw_list(
        self: Self,
        routing: Union[RiotRegion, RiotPlatform],
        path: str
    ) -> list[str]:
        """
        Make an HTTP GET request expecting a list of strings.

        Used for endpoints that return simple lists (e.g., match IDs).

        Args:
            routing: Regional or platform routing value.
            path: API endpoint path

        Returns:
            List of strings from the response.

        Raises:
            Same exceptions as _request.
        """
        url = self._build_url(routing, path)
        self._logger.debug("Requesting raw list: %s", url)

        await acquire_riot(routing.value)
        try:
            response = await self._session.get(
                url,
                timeout=self._config.timeout_seconds
            )
        except aiohttp.client_exceptions.ConnectionTimeoutError as exc:
            raise RiotAPITimeoutError(
                message=f"Request times out after {self._config.timeout_seconds}s"
            ) from exc
        except aiohttp.client_exceptions.ClientResponseError as exc:
            raise RiotAPIError(f"Request failed: {exc}") from exc

        self._check_response_status(response)

        try:
            return await response.json()
        except (ContentTypeError, ValueError) as exc:
            self._logger.error("Failed to parse response: %s", exc)
            raise RiotAPIError(f"Failed to parse response: {exc}") from exc


    async def _handle_response(
        self: Self,
        response: ClientResponse,
        response_model: Type[T]
    ) -> T:
        """
        Handle response status and parse body.

        Args:
            response: HTTP response object.
            response_model: Pydantic model to parse into.

        Returns:
            Parsed response as the specified model type.
        """
        self._check_response_status(response)

        try:
            data = await response.json()
            return response_model.model_validate(data)
        except (ContentTypeError, ValueError) as exc:
            self._logger.error("Failed to parse response: %s", exc)
            raise RiotAPIError(f"Invalid response format: {exc}") from exc

    def _check_response_status(
        self: Self,
        response: ClientResponse
    ) -> None:
        """
        Check response status and raise appropriate exception.

        Args:
            response: HTTP response object.

        Raises:
            RiotAPIAuthenticationError: For 401/403 responses.
            RiotAPINotFoundError: For 404 responses.
            RiotAPIRateLimitError: For 429 responses.
            RiotAPIServerError: For 5xx responses.
            RiotAPIError: For other error responses.
        """
        if response.ok:
            return

        status = response.status
        self._logger.warning("API returned status %s", status)

        match status:
            case 401:
                raise RiotAPIAuthenticationError(
                    "Invalid or expired API key"
                )
            case 403:
                raise RiotAPIAuthenticationError(
                    "Access forbidden - check API key permissions"
                )
            case 404:
                raise RiotAPINotFoundError("Resource not found")
            case 429:
                retry_after = response.headers.get("Retry-After")
                raise RiotAPIRateLimitError(
                    "Rate limit exceeded",
                    retry_after=int(retry_after) if retry_after else None
                )
            case _ if 500 <= status < 600:
                raise RiotAPIServerError(
                    f"Server error: {status}",
                    status_code=status
                )
            case _:
                raise RiotAPIError(
                    f"Unexpected status: {status}",
                    status_code=status
                )

    def _validate_puuid(self: Self, puuid: str) -> None:
        """Validate that a PUUID is exactly 78 characters."""
        if not puuid or len(puuid) != 78:
            raise RiotAPIValidationError("Invalid PUUID format (must be 78 characters)")

    def _region_to_platform(self: Self, region: str) -> RiotPlatform:
        """Convert a region code (e.g. 'na') to a platform routing value."""
        region_lower = region.lower()
        if region_lower not in REGION_TO_PLATFORM:
            raise RiotAPIValidationError(f"Unknown region: {region}")
        return REGION_TO_PLATFORM[region_lower]

    async def close(self: Self) -> None:
        """Close the HTTP session."""
        await self._session.close()

    def __enter__(self: Self):
        """Context manager entry."""
        return self

    def __exit__(self: Self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session."""
        self.close()
        return False
