"""
FastAPI dependency injection providers for Riot API clients.

Provides dependency functions and type aliases for injecting Riot API
clients into FastAPI route handlers.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from .config import RiotAPIConfig
from .facade import RiotAPIFacade
from .clients.account_client import AccountClient
from .clients.summoner_client import SummonerClient
from .clients.league_client import LeagueClient
from ...dependencies import RIOT_API_KEY


@lru_cache
def get_riot_api_config() -> RiotAPIConfig:
    """
    Get cached Riot API configuration.

    Uses lru_cache to ensure configuration is created once per process.

    Returns:
        Immutable Riot API configuration.
    """
    return RiotAPIConfig(api_key=RIOT_API_KEY)


def get_account_client(
    config: Annotated[RiotAPIConfig, Depends(get_riot_api_config)]
) -> AccountClient:
    """
    Get AccountClient instance for dependency injection.

    Args:
        config: Injected configuration.

    Returns:
        AccountClient instance.
    """
    return AccountClient(config)


def get_summoner_client(
    config: Annotated[RiotAPIConfig, Depends(get_riot_api_config)]
) -> SummonerClient:
    """
    Get SummonerClient instance for dependency injection.

    Args:
        config: Injected configuration.

    Returns:
        SummonerClient instance.
    """
    return SummonerClient(config)


def get_league_client(
    config: Annotated[RiotAPIConfig, Depends(get_riot_api_config)]
) -> LeagueClient:
    """
    Get LeagueClient instance for dependency injection.

    Args:
        config: Injected configuration.

    Returns:
        LeagueClient instance.
    """
    return LeagueClient(config)


def get_riot_api(
    config: Annotated[RiotAPIConfig, Depends(get_riot_api_config)]
) -> RiotAPIFacade:
    """
    Get RiotAPIFacade instance for dependency injection.

    This is the primary dependency for route handlers that need
    to interact with the Riot API.

    Args:
        config: Injected configuration.

    Returns:
        RiotAPIFacade instance.

    Example:
        @router.get("/summoner/{name}/{tag}")
        def get_summoner(
            name: str,
            tag: str,
            riot_api: RiotAPIDep,
        ):
            return riot_api.get_summoner(name, tag)
    """
    return RiotAPIFacade(config)


# Type aliases for cleaner route handler annotations
RiotAPIDep = Annotated[RiotAPIFacade, Depends(get_riot_api)]
AccountClientDep = Annotated[AccountClient, Depends(get_account_client)]
SummonerClientDep = Annotated[SummonerClient, Depends(get_summoner_client)]
LeagueClientDep = Annotated[LeagueClient, Depends(get_league_client)]
