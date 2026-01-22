"""
Riot API Client Library.

Provides modular clients for interacting with Riot Games APIs.

Usage:
    from app.internal.riot_api import RiotAPIFacade, RiotAPIConfig, RiotAPIDep

    # With dependency injection (recommended)
    @router.get("/summoner/{name}/{tag}")
    def get_summoner(name: str, tag: str, riot_api: RiotAPIDep):
        return riot_api.get_summoner(name, tag)

    # Direct instantiation
    config = RiotAPIConfig(api_key="RGAPI-xxx")
    with RiotAPIFacade(config) as riot_api:
        summoner = riot_api.get_summoner("PlayerName", "TAG")
"""

# Configuration
from .config import (
    RiotAPIConfig,
    RiotRegion,
    RiotPlatform,
    REGION_TO_PLATFORM,
    PLATFORM_TO_REGION,
)

# Exceptions
from .exceptions import (
    RiotAPIError,
    RiotAPIAuthenticationError,
    RiotAPINotFoundError,
    RiotAPIRateLimitError,
    RiotAPIServerError,
    RiotAPIValidationError,
    RiotAPITimeoutError,
)

# Models
from .models import (
    RiotAccount,
    RiotError,
    AccountRegion,
    SummonerInfo,
    LeagueEntry,
    #MatchMetadata,
    #MatchParticipant,
    #MatchTeam,
    #MatchInfo,
    #Match,
    #MatchTimeline,
    SummonerProfile,
    SummonerLeagueInfo,
)

# Facade
from .facade import RiotAPIFacade

# HTTP Error Translation
from .http_errors import riot_exception_to_http

# Dependencies
from .dependencies import (
    get_riot_api_config,
    get_riot_api,
    get_account_client,
    get_summoner_client,
    get_league_client,
    #get_match_client,
    RiotAPIDep,
    AccountClientDep,
    SummonerClientDep,
    LeagueClientDep,
    #MatchClientDep,
)

# Clients (for advanced usage)
from .clients import (
    AccountClient,
    SummonerClient,
    LeagueClient,
    #MatchClient,
)


__all__ = [
    # Config
    "RiotAPIConfig",
    "RiotRegion",
    "RiotPlatform",
    "REGION_TO_PLATFORM",
    "PLATFORM_TO_REGION",
    # Exceptions
    "RiotAPIError",
    "RiotAPIAuthenticationError",
    "RiotAPINotFoundError",
    "RiotAPIRateLimitError",
    "RiotAPIServerError",
    "RiotAPIValidationError",
    "RiotAPITimeoutError",
    # Models
    "RiotAccount",
    "RiotError",
    "AccountRegion",
    "SummonerInfo",
    "LeagueEntry",
    #"MatchMetadata",
    #"MatchParticipant",
    #"MatchTeam",
    #"MatchInfo",
    #"Match",
    #"MatchTimeline",
    "SummonerProfile",
    "SummonerLeagueInfo",
    # Facade
    "RiotAPIFacade",
    # HTTP Errors
    "riot_exception_to_http",
    # Dependencies
    "get_riot_api_config",
    "get_riot_api",
    "get_account_client",
    "get_summoner_client",
    "get_league_client",
    #"get_match_client",
    "RiotAPIDep",
    "AccountClientDep",
    "SummonerClientDep",
    "LeagueClientDep",
    #"MatchClientDep",
    # Clients
    "AccountClient",
    "SummonerClient",
    "LeagueClient",
    #"MatchClient",
]
