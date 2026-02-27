"""
Client for League of Legends Summoner API endpoints.

Handles summoner profile data retrieval.
Uses platform routing (na1, euw1, etc.).
"""

from typing import Self

from ..base import RiotAPIBase
from ..config import RiotPlatform
from ..models import SummonerInfo


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

