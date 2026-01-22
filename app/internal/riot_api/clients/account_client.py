"""
Client for Riot Account API endpoints.

Handles Riot ID to PUUID resolution and region lookup.
Uses regional routing (americas, europe, asia, sea).
"""

from typing import Optional, Self

from .. import RiotAPINotFoundError
from ..base import RiotAPIBase
from ..config import RiotAPIConfig, RiotRegion
from ..models import RiotAccount, RiotError, AccountRegion
from ..exceptions import RiotAPIValidationError


class AccountClient(RiotAPIBase):
    """
    Client for Riot Account API endpoints.

    Handles:
    - Converting Riot ID (name#tag) to PUUID
    - Looking up account info by PUUID
    - Determining active region for a player

    Uses regional routing endpoints (americas, europe, asia, sea).
    """

    def __init__(
        self: Self,
        config: RiotAPIConfig,
        default_region: Optional[RiotRegion] = None
    ):
        """
        Initialize the account client.

        Args:
            config: API configuration.
            default_region: Default regional routing (defaults to config value).
        """
        super().__init__(config)
        self._default_region = default_region or config.default_account_region

    async def get_by_riot_id(
        self: Self,
        game_name: str,
        tag_line: str,
        region: Optional[RiotRegion] = None
    ) -> RiotAccount:
        """
        Get account information by Riot ID (name#tag).

        Args:
            game_name: Player's display name.
            tag_line: Player's tag (without #).
            region: Regional routing to use (defaults to configured region)

        Returns:
            Account information including PUUID.

        Raises:
            RiotAPIValidationError: If game_name or tag_line is invalid.
            RiotAPINotFoundError: If account does not exist.
        """
        self._validate_riot_id(game_name, tag_line)

        routing = region or self._default_region
        path = f"riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"


        return await self._request(routing, path, RiotAccount)

    async def get_by_puuid(
        self: Self,
        puuid: str,
        region: Optional[RiotRegion] = None
    ) -> RiotAccount:
        """
        Get account information by PUUID.

        Args:
            puuid: Player's universal unique identifier
            region: Regional routing to use.

        Returns:
            Account information.

        Raises:
            RiotAPIValidationError: If PUUID format is invalid.
            RIOTAPINotFoundError: If account does not exist.
        """
        self._validate_puuid(puuid)

        routing = region or self._default_region
        path = f"riot/account/v1/accounts/by-puuid/{puuid}"

        return await self._request(routing, path, RiotAccount)

    async def get_active_region(
        self: Self,
        game: str,
        puuid: str,
        region: Optional[RiotRegion] = None
    ) -> str:
        """
        Get the region where a player is aactive for a specific game.

        Args:
            game: Game identifier (e.g., "lol", "val", "lor").
            puuid: Player's universal unique identifier.
            region: Regional routing to use.

        Returns:
            Region code (e.g., "na", "euw", "kr").

        Raises:
            RiotAPIValidationError: If PUUID format is invalid.
            RIOTAPINotFoundError: If account/region not found.
        """
        self._validate_puuid(puuid)

        routing = region or self._default_region
        path = f"riot/account/v1/region/by-game/{game}/by-puuid/{puuid}"

        response = await self._request(routing, path, AccountRegion)
        return response.region

    def _validate_riot_id(
        self: Self,
        game_name: str,
        tag_line: str
    ) -> None:
        """
        Validate Riot ID components.

        Args:
            game_name: Player's display name.
            tag_line: Player's tag.

        Raises:
            RiotAPIValidationError: If validation fails.
        """
        if not game_name or not game_name.strip():
            raise RiotAPIValidationError("Game name cannot be empty")

        if not tag_line or not tag_line.strip():
            raise RiotAPIValidationError("Tag line cannot be empty")

        if len(game_name) > 16:
            raise RiotAPIValidationError(
                "Game name exceeds maximum length (16 characters)"
            )

        if len(tag_line) > 5:
            raise RiotAPIValidationError(
                "Tag line exceeds maximum length (5 characters)"
            )

    def _validate_puuid(self, puuid: str) -> None:
        """
        Validate PUUID format.

        Args:
            puuid: The PUUID to validate.

        Raises:
            RiotAPIValidationError: If PUUID format is invalid.
        """
        if not puuid or len(puuid) != 78:
            raise RiotAPIValidationError(
                "Invalid PUUID format (must be 78 characters)"
            )

