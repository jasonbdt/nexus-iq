"""
Client for League of Legends Summoner API endpoints.

Handles summoner profile data retrieval.
Uses platform routing (na1, euw1, etc.).
"""

from typing import Self

from ..base import RiotAPIBase
from ..config import RiotPlatform, REGION_TO_PLATFORM
from ..models import SummonerInfo
from ..exceptions import RiotAPIValidationError


class SummonerClient(RiotAPIBase):
    """
    Client for League of Legends Summoner API endpoints.

    Handles summoner profile data retrieval including:
    - Summoner level
    - Profile icon ID
    - Revision date (last update timestamp)

    Uses platform routing endpoints (na1, euw1, kr, etc.).
    """

    async def get_by_puuid(
        self: Self,
        puuid: str,
        platform: RiotPlatform
    ) -> SummonerInfo:
        """
        Get summoner information by PUUID.

        Args:
            puuid: Player's universal unique identifier.
            platform: Platform routing value (e.g., NA1, EUW1).

        Returns:
            Summoner profile information.

        Raises:
            RiotAPIValidationError: If PUUID format is invalid.
            RiotAPINotFoundError: If summoner does not exist.
        """
        self._validate_puuid(puuid)

        path = f"lol/summoner/v4/summoners/by-puuid/{puuid}"
        return await self._request(platform, path, SummonerInfo)

    async def get_by_puuid_with_region(
        self,
        puuid: str,
        region: str,
    ) -> SummonerInfo:
        """
        Get summoner information using a region code.

        Convenience method that converts region code to platform routing.

        Args:
            puuid: Player's universal unique identifier.
            region: Region code (e.g., "na", "euw", "kr").

        Returns:
            Summoner profile information.

        Raises:
            RiotAPIValidationError: If PUUID or region is invalid.
            RiotAPINotFoundError: If summoner does not exist.
        """
        platform = self._region_to_platform(region)
        return await self.get_by_puuid(puuid, platform)

    def _region_to_platform(self, region: str) -> RiotPlatform:
        """
        Convert a region code to platform routing value.

        Args:
            region: Region code (e.g., "na", "euw").

        Returns:
            Corresponding platform routing value.

        Raises:
            RiotAPIValidationError: If region is unknown.
        """
        region_lower = region.lower()
        if region_lower not in REGION_TO_PLATFORM:
            raise RiotAPIValidationError(f"Unknown region: {region}")
        return REGION_TO_PLATFORM[region_lower]

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
