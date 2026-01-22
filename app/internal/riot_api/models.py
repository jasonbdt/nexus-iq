"""
Pydantic models for Riot API responses.

Provides type-safe models for parsing API responses and composite models
for the facade layer.
"""

from datetime import datetime, timezone
from typing import Any, Optional, Self

from pydantic import BaseModel, Field, computed_field


# =============================================================================
# Standard API Models
# =============================================================================

class RiotError(BaseModel):
    """Response model for errors."""
    status: int
    message: str

# =============================================================================
# Account API Models
# =============================================================================

class RiotAccount(BaseModel):
    """Response model for account/v1 endpoints."""
    puuid: str
    game_name: str = Field(alias="gameName")
    tag_line: str = Field(alias="tagLine")

    model_config = {"populate_by_name": True}


class AccountRegion(BaseModel):
    """Response model for region lookup endpoint."""
    region: str


# =============================================================================
# Summoner API Models
# =============================================================================

class SummonerInfo(BaseModel):
    """Response model for summoner/v4 endpoints."""
    # id: str
    # account_id: str = Field(alias="accountId")
    puuid: str
    profile_icon_id: int = Field(alias="profileIconId")
    revision_date: int = Field(alias="revisionDate")
    summoner_level: int = Field(alias="summonerLevel")

    model_config = {"populate_by_name": True}

    @computed_field
    @property
    def revision_datetime(self: Self) -> datetime:
        """Convert revision date from milliseconds to UTC datetime."""
        return datetime.fromtimestamp(self.revision_date / 1000, tz=timezone.utc)


# =============================================================================
# League API Models
# =============================================================================

class LeagueEntry(BaseModel):
    """Response model for league/v4 entries."""
    league_id: str = Field(alias="leagueId")
    queue_type: str = Field(alias="queueType")
    tier: str
    rank: str
    # summoner_id: str = Field(alias="summonerId")
    league_points: int = Field(alias="leaguePoints")
    wins: int
    losses: int
    veteran: bool = False
    inactive: bool = False
    fresh_blood: bool = Field(False, alias="freshBlood")
    hot_streak: bool = Field(False, alias="hotStreak")

    model_config = {"populate_by_name": True}


# =============================================================================
# Composite/Facade Models
# =============================================================================

class SummonerProfile(BaseModel):
    """
    Aggregated summoner profile from multiple API calls.

    Used by RiotAPIFacade.get_summoner() to return complete profile data.
    """
    puuid: str
    region: str
    summoner_name: str
    tag_line: str
    summoner_level: int
    profile_icon: int
    leagues: list[LeagueEntry]
    revision_date: datetime

    @computed_field
    @property
    def riot_id(self: Self) -> str:
        return f"{self.summoner_name}#{self.tag_line}"


class SummonerLeagueInfo(BaseModel):
    """
    Processed league entry for API response.

    Simplified version of LeagueEntry for the facade layer.
    """
    league_id: str
    queue_type: str
    tier: str
    rank: str
    wins: int
    losses: int
    league_points: int

    @computed_field
    @property
    def total_games(self) -> int:
        """Total games played in this queue."""
        return self.wins + self.losses

    @computed_field
    @property
    def win_rate(self) -> float:
        """Win rate percentage."""
        if self.total_games == 0:
            return 0.0
        return round((self.wins / self.total_games) * 100, 1)
