"""
Domain-specific Riot API clients.

Each client handles a specific API domain:
- AccountClient: Riot ID resolution and region lookup
- SummonerClient: Summoner profile data
- LeagueClient: Ranked/league data
- MatchClient: Match history and timeline data
"""

from .account_client import AccountClient
from .summoner_client import SummonerClient
from .league_client import LeagueClient
from .match_client import MatchClient

__all__ = [
    "AccountClient",
    "SummonerClient",
    "LeagueClient",
    "MatchClient",
]
