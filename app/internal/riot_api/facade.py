"""
High-level facade for Riot API operations.

Composes domain clients to provide convenient methods for common use cases.
This is the primary interface for application code to interact with the Riot API.
"""

from typing import List, Optional, Self, Union

from . import RiotAPINotFoundError
from .config import RiotAPIConfig, REGION_TO_PLATFORM
from .models import RiotError, SummonerProfile, SummonerLeagueInfo, Match  # , Match, MatchTimeline
from .clients.account_client import AccountClient
from .clients.summoner_client import SummonerClient
from .clients.league_client import LeagueClient
from .clients.match_client import MatchClient
from ..logging import get_logger


logger = get_logger(__name__)


class RiotAPIFacade:
    """
    High-level facade for Riot API operations.

    Composes domain clients to provide convenient methods for common
    use cases. Handles the coordination between multiple API calls.

    Example:
        config = RiotAPIConfig(api_key="RGAPI-xxx")
        with RiotAPIFacade(config) as riot_api:
            profile = riot_api.get_summoner("PlayerName", "TAG")
            leagues = riot_api.get_summoner_leagues(profile.region, profile.puuid)
    """

    def __init__(
        self: Self,
        config: RiotAPIConfig,
        account_client: Optional[AccountClient] = None,
        summoner_client: Optional[SummonerClient] = None,
        league_client: Optional[LeagueClient] = None,
        match_client: Optional[MatchClient] = None
    ):
        """
        Initialize the facade with configuration and optional client overrides.

        Args:
            config: API configuration.
            account_client: Optional pre-configured account client (for testing).
            summoner_client: Optional pre-configured summoner client (for testing).
            league_client: Optional pre-configured league client (for testing).
            match_client: Optional pre-configured match client (for testing).
        """
        self._config = config
        self._account_client = account_client or AccountClient(config)
        self._summoner_client = summoner_client or SummonerClient(config)
        self._league_client = league_client or LeagueClient(config)
        self._match_client = match_client or MatchClient(config)

        logger.info("RiotAPIFacade initialized successfully")

    # =========================================================================
    # Summoner Methods
    # =========================================================================

    async def get_summoner(
        self: Self,
        player_name: str,
        tag_line: str,
    ) -> Union[SummonerProfile, RiotError]:
        """
        Get complete summoner profile by Riot ID.

        Resolves Riot ID to PUUID, determines region, and fetches
        summoner profile data in a single call.

        Args:
            player_name: Player's display name.
            tag_line: Player's tag (without #).

        Returns:
            Aggregated summoner profile with all relevant data.

        Raises:
            RiotAPINotFoundError: If summoner does not exist.
            RiotAPIError: For other API errors.
        """
        logger.debug(f"Getting summoner: {player_name}#{tag_line}")

        # Step 1: Resolve Riot ID to account info (includes PUUID)
        try:
            account = await self._account_client.get_by_riot_id(player_name, tag_line)
        except RiotAPINotFoundError:
            raise RiotAPINotFoundError(message="Summoner not found")

        # Step 2: Get region for LoL
        region = await self._account_client.get_active_region("lol", account.puuid)

        # Step 3: Get summoner profile from region-specific endpoint
        summoner = await self._summoner_client.get_by_puuid_with_region(
            account.puuid, region
        )

        # Step 4: Get summoner league entries
        leagues = await self._league_client.get_entries_by_puuid_with_region(
            account.puuid, region
        )

        return SummonerProfile(
            puuid=account.puuid,
            region=region,
            summoner_name=account.game_name,
            tag_line=account.tag_line,
            summoner_level=summoner.summoner_level,
            profile_icon=summoner.profile_icon_id,
            revision_date=summoner.revision_datetime,
            leagues=leagues
        )

    async def get_summoner_by_puuid(self: Self, puuid: str) -> Optional[SummonerProfile]:
        """
        Get summoner profile by PUUID.

        Useful when you already have the PUUID and need to refresh data.

        Args:
            puuid: Player's universal unique identifier.

        Returns:
            Summoner profile or None if not found.
        """
        logger.debug(f"Getting summoner by PUUID: {puuid[:8]}...")

        try:
            # Get account info to get name/tag
            account = await self._account_client.get_by_puuid(puuid)
            region = await self._account_client.get_active_region("lol", puuid)
            summoner = await self._summoner_client.get_by_puuid_with_region(puuid, region)
            leagues = await self._league_client.get_entries_by_puuid_with_region(puuid, region)

            return SummonerProfile(
                puuid=puuid,
                region=region,
                summoner_name=account.game_name,
                tag_line=account.tag_line,
                summoner_level=summoner.summoner_level,
                profile_icon=summoner.profile_icon_id,
                revision_date=summoner.revision_datetime,
                leagues=leagues
            )
        except Exception as e:
            logger.warning(f"Failed to get summoner by PUUID: {e}")
            return None

    # =========================================================================
    # League Methods
    # =========================================================================

    # TODO: Determine if this method is really needed
    async def get_summoner_leagues(
        self: Self,
        region: str,
        puuid: str,
    ) -> List[SummonerLeagueInfo]:
        """
        Get league entries for a summoner.

        Args:
            region: Region code (e.g., "na", "euw", "kr").
            puuid: Player's universal unique identifier.

        Returns:
            List of processed league entries (one per queue type).
        """
        logger.debug(f"Getting leagues for PUUID: {puuid[:8]}... in region: {region}")

        entries = await self._league_client.get_entries_by_puuid_with_region(puuid, region)

        return [
            SummonerLeagueInfo(
                league_id=entry.league_id,
                queue_type=entry.queue_type,
                tier=entry.tier,
                rank=entry.rank,
                wins=entry.wins,
                losses=entry.losses,
                league_points=entry.league_points,
            ) for entry in entries
        ]

    # =========================================================================
    # Match Methods
    # =========================================================================

    async def get_recent_matches(
        self: Self,
        puuid: str,
        region: str,
        count: int = 10
    ) -> list[Match]:
        """
        Get recent match details for a player.

        Fetches match IDs and then retrieves full match data for each.

        Args:
            puuid: Player's universal unique identifier
            region: Region code (e.g., "na", "euw", "kr").
            count: Number of matches to retrieve (max 100).

        Returns:
            List of full match data objects.
        """
        logger.debug(f"Getting {count} recent matches for PUUID: {puuid[:8]}...")

        match_ids = await self._match_client.get_match_ids_by_puuid_with_region(puuid, region, count)

        # Get full match data for each matchId
        matches = []
        for match_id in match_ids:
            try:
                match = await self._match_client.get_match_with_region(match_id, region)
                matches.append(match)
            except Exception as e:
                logger.warning(f"Failed to fetch match {match_id}: {e}")
                continue

        return matches
