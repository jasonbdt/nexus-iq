"""
Client for League of Legends Match API endpoints.

Handles match history and timeline data retrieval.
Uses regional routing (americas, europe, asia, sea).
"""

from typing import Optional, Self

from ..base import RiotAPIBase
from ..config import RiotRegion, RiotPlatform, PLATFORM_TO_REGION, REGION_TO_PLATFORM
from ..models import Match
from ..exceptions import RiotAPIValidationError


class MatchClient(RiotAPIBase):
    """
    Client for League of Legends Match API endpoints.

    Handles match data retrieval including:
    - Match IDs by PUUID
    - Full match details
    - Match timeline (frame-by-frame data)

    Uses regional routing endpoints (americas, europe, asia, sea).
    """

    async def get_match_ids_by_puuid(
        self: Self,
        puuid: str,
        region: RiotRegion,
        count: int = 20,
        start: int = 0,
        queue: Optional[int] = None,
        match_type: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> list[str]:
        """
        Get list of match IDs for a player.

        Args:
            puuid: Player's universal unique identifier.
            region: Regional routing value (americas, europe, asia, sea).
            count: Number of match IDs to return (1-100, default 20).
            start: Starting index for pagination (default 0)
            queue: Filter by queue ID (e.g., 420 for ranked solo)
            match_type: Filter by match type (ranked, normal, tourney, tutorial).
            start_time: Filter matches after this epoch timestamp (seconds).
            end_time: Filter matches before this epoch timestamp (seconds).

        Returns:
            List of match IDs (e.g., ["EUW1_4567890123", ...]).

        Raises:
            RiotAPIValidationError: If PUUID format is invalid.
        """
        self._validate_puuid(puuid)

        # Build query parameters
        params = [f"count={min(max(count, 1), 100)}", f"start={start}"]
        if queue is not None:
            params.append(f"queue={queue}")
        if match_type is not None:
            params.append(f"type={match_type}")
        if start_time is not None:
            params.append(f"startTime={start_time}")
        if end_time is not None:
            params.append(f"endTime={end_time}")

        query_string = "&".join(params)
        path = f"lol/match/v5/matches/by-puuid/{puuid}/ids?{query_string}"

        return await self._request_raw_list(region, path)

    async def get_match_ids_by_puuid_with_region(
        self: Self,
        puuid: str,
        region: str,
        count: int = 20,
        start: int = 0
    ) -> list[str]:
        """
        Get match IDs using a region code string.

        Convenience method that converts region code to regional routing.

        Args:
            puuid: Player's universal unique identifier.
            region: Region code (e.g., "na", "euw", "kr").
            count: Number of Match IDs to return.
            start: Starting index for pagination.

        Returns:
            List of match IDs.
        """
        platform = self._region_code_to_platform(region)
        region = self._platform_to_region(platform)

        return await self.get_match_ids_by_puuid(puuid, region, count, start)

    async def get_match(
        self: Self,
        match_id: str,
        region: RiotRegion
    ) -> Match:
        """
        Get detailed match information.

        Args:
            match_id: Match ID (e.g., "EUW1_4567890123").
            region: Regional routing value.

        Returns:
            Full match data including participants, teams, and metadata.

        Raises:
            RiotAPINotFoundError: If match does not exist.
        """
        path = f"lol/match/v5/matches/{match_id}"
        return await self._request(region, path, Match)

    async def get_match_with_region(
        self: Self,
        match_id: str,
        region: str
    ) -> Match:
        """
        Get match using a region code string.

        Args:
            match_id: Match ID.
            region: Region code (e.g., "na", "euw").

        Returns:
            Full match data.
        """
        platform = self._region_code_to_platform(region)
        region = self._platform_to_region(platform)

        return await self.get_match(match_id, region)

    def _platform_to_region(self: Self, platform: RiotPlatform) -> RiotRegion:
        """
        Convert platform to regional routing.

        Args:
            platform: Platform routing value.

        Returns:
            Corresponding regional routing value.

        Raises:
            RiotAPIValidationError: If platform is unknown
        """
        if platform not in PLATFORM_TO_REGION:
            raise RiotAPIValidationError(f"Unknown platform: {platform}")
        return PLATFORM_TO_REGION[platform]

    def _region_code_to_platform(self: Self, region: str) -> RiotPlatform:
        """
        Convert region code to platform.

        Args:
            region: Region code (e.g., "na", "euw").

        Returns:
            Corresponding platform routing value.

        Raises:
            RiotAPIValidationError: If region code is unknown.
        """
        region_lower = region.lower()
        if region_lower not in REGION_TO_PLATFORM:
            raise RiotAPIValidationError(f"Unknown region: {region}")
        return REGION_TO_PLATFORM[region_lower]

    def _validate_puuid(self: Self, puuid: str) -> None:
        """
        Validate PUUID format.

        Args:
            puuid: The PUUID to validate.

        Raises:
            RiotAPIValidationError: If PUUID format is invalid.
        """
        if not puuid or len(puuid) != 78:
            raise RiotAPIValidationError(
                message="Invalid PUUID format (must be 78 characters)"
            )
