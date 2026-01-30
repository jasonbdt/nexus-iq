"""
Client for League of Legends League API endpoints.

Handles ranked/league data retrieval.
Uses platform routing (na1, euw1, etc.).
"""

from typing import List

from ..base import RiotAPIBase
from ..config import RiotPlatform, REGION_TO_PLATFORM
from ..models import LeagueEntry
from ..exceptions import RiotAPIValidationError


class LeagueClient(RiotAPIBase):
    """
    Client for League of Legends League API endpoints.

    Handles ranked league data retrieval including:
    - Queue type (Solo/Duo, Flex)
    - Tier and rank
    - LP, wins, losses
    - Special statuses (veteran, hot streak, etc.)

    Uses platform routing endpoints (na1, euw1, kr, etc.).
    """

    async def get_entries_by_puuid(
        self,
        puuid: str,
        platform: RiotPlatform,
    ) -> List[LeagueEntry]:
        """
        Get league entries for a summoner by PUUID.

        Args:
            puuid: Player's universal unique identifier.
            platform: Platform routing value (e.g., NA1, EUW1).

        Returns:
            List of league entries (one per queue type the player is ranked in).

        Raises:
            RiotAPIValidationError: If PUUID format is invalid.
        """
        self._validate_puuid(puuid)

        path = f"lol/league/v4/entries/by-puuid/{puuid}"
        return await self._request_list(platform, path, LeagueEntry)

    async def get_entries_by_puuid_with_region(
        self,
        puuid: str,
        region: str,
    ) -> List[LeagueEntry]:
        """
        Get league entries using a region code.

        Convenience method that converts region code to platform routing.

        Args:
            puuid: Player's universal unique identifier.
            region: Region code (e.g., "na", "euw", "kr").

        Returns:
            List of league entries.

        Raises:
            RiotAPIValidationError: If PUUID or region is invalid.
        """
        platform = self._region_to_platform(region)
        return await self.get_entries_by_puuid(puuid, platform)

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
