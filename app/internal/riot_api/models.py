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
# Match API Models
# =============================================================================

class MatchMetadata(BaseModel):
    """Metadata for a match."""
    data_version: str = Field(alias="dataVersion")
    match_id: str = Field(alias="matchId")
    participants: list[str]

    model_config = {"populate_by_name": True}


class MatchParticipantPerkStats(BaseModel):
    defense: int
    flex: int
    offense: int

    model_config = {"populate_by_name": True}


class MatchParticipantPerkStyleSelection(BaseModel):
    perk: int
    var1: int
    var2: int
    var3: int

    model_config = {"populate_by_name": True}


class MatchParticipantPerkStyle(BaseModel):
    description: str
    selections: list[MatchParticipantPerkStyleSelection]
    style: int

    model_config = {"populate_by_name": True}


class MatchParticipantPerks(BaseModel):
    """Participants perks within a match."""
    stat_perks: MatchParticipantPerkStats = Field(alias="statPerks")
    styles: list[MatchParticipantPerkStyle]

    model_config = {"populate_by_name": True}


class MatchParticipant(BaseModel):
    """Participant data within a match."""
    puuid: str
    summoner_name: str = Field(alias="summonerName")
    riot_id_game_name: str = Field(alias="riotIdGameName")
    riot_id_tagline: str = Field(alias="riotIdTagline")
    champion_id: int = Field(alias="championId")
    champion_name: str = Field(alias="championName")
    champion_level: int = Field(alias="champLevel")
    time_played: int = Field(alias="timePlayed")
    team_id: int = Field(alias="teamId")
    win: bool

    # KDA stats
    kills: int
    deaths: int
    assists: int

    # Kill stats
    double_kills: int = Field(alias="doubleKills")
    triple_kills: int = Field(alias="tripleKills")
    quadra_kills: int = Field(alias="quadraKills")
    penta_kills: int = Field(alias="pentaKills")
    largest_multi_kill: int = Field(alias="largestMultiKill")

    # Damage stats
    damage_dealt_to_champions: int = Field(alias="totalDamageDealtToChampions")
    damage_taken: int = Field(alias="totalDamageTaken")

    # CS stats
    total_minions_killed: int = Field(alias="totalMinionsKilled")
    neutral_minions_killed: int = Field(alias="neutralMinionsKilled")

    # Gold and damage
    gold_earned: int = Field(alias="goldEarned")
    gold_spent: int = Field(alias="goldSpent")
    total_damage_dealt_to_champions: int = Field(alias="totalDamageDealtToChampions")

    # Items (0-6)
    item0: int = 0
    item1: int = 0
    item2: int = 0
    item3: int = 0
    item4: int = 0
    item5: int = 0
    item6: int = 0 # Trinket

    # Runes
    perks: MatchParticipantPerks

    # Vision
    vision_score: int = Field(0, alias="visionScore")
    wards_placed: int = Field(0, alias="wardsPlaced")
    wards_killed: int = Field(0, alias="wardsKilled")
    vision_wards_bought: int = Field(0, alias="visionWardsBoughtInGame")

    # Position
    team_position: str = Field("", alias="teamPosition")
    lane: str

    model_config = {"populate_by_name": True}

    @computed_field
    @property
    def kda(self: Self) -> float:
        """Calculate KDA ratio."""
        if self.deaths == 0:
            return float(self.kills + self.assists)

        return round((self.kills + self.assists) / self.deaths, 2)

    @computed_field
    @property
    def cs(self: Self) -> int:
        """Total creep score."""
        return self.total_minions_killed + self.neutral_minions_killed


class MatchTeamBans(BaseModel):
    """Team bans within a match."""
    champion_id: int = Field(alias="championId")
    pick_turn: int = Field(alias="pickTurn")


class MatchObjective(BaseModel):
    """DTO for Match objectives."""
    first: bool
    kills: int


class MatchTeamObjectives(BaseModel):
    """Team objectives within a match."""
    baron: MatchObjective
    champion: MatchObjective
    dragon: MatchObjective
    horde: MatchObjective
    inhibitor: MatchObjective
    rift_herald: MatchObjective = Field(alias="riftHerald")
    tower: MatchObjective


class MatchTeam(BaseModel):
    """Team data within a match."""
    team_id: int = Field(alias="teamId")
    bans: list["MatchTeamBans"]
    objectives: MatchTeamObjectives
    win: bool

    model_config = {"populate_by_name": True}


class MatchInfo(BaseModel):
    """Match information (game data)."""
    game_creation: int = Field(alias="gameCreation")
    game_duration: int = Field(alias="gameDuration")
    game_start_timestamp: int = Field(alias="gameStartTimestamp")
    game_end_timestamp: Optional[int] = Field(None, alias="gameEndTimestamp")
    game_id: int = Field(alias="gameId")
    game_mode: str = Field(alias="gameMode")
    game_name: str = Field(alias="gameName")
    game_type: str = Field(alias="gameType")
    game_version: str = Field(alias="gameVersion")
    map_id: int = Field(alias="mapId")
    queue_id: int = Field(alias="queueId")
    platform_id: str = Field(alias="platformId")
    participants: list[MatchParticipant]
    teams: list[MatchTeam]

    model_config = {"populate_by_name": True}

    @computed_field
    @property
    def game_creation_datetime(self: Self) -> datetime:
        """Convert game creation timestamp to UTC datetime."""
        return datetime.fromtimestamp(self.game_creation / 1000, tz=timezone.utc)

    @computed_field
    @property
    def game_end_datetime(self: Self) -> Optional[datetime]:
        """Convert game end timestamp to UTC datetime."""
        if self.game_end_timestamp:
            return datetime.fromtimestamp(
                self.game_end_timestamp / 1000,
                tz=timezone.utc
            )

        return None

    @computed_field
    @property
    def duration_minutes(self: Self) -> float:
        """Game duration in minutes."""
        return round(self.game_duration / 60, 1)


class Match(BaseModel):
    """Complete match data from match/v5 endpoint."""
    metadata: MatchMetadata
    info: MatchInfo


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
