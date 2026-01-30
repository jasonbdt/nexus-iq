from typing import Optional, Self, Any
from datetime import datetime, timezone

from sqlalchemy import DateTime, func, JSON
from sqlmodel import Column, Field, Relationship, SQLModel
from pydantic import BaseModel, computed_field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    avatarName: str = Field(index=True, nullable=False)
    emailAddress: str = Field(unique=True, nullable=False)
    password: str = Field(nullable=False)
    is_active: bool = Field(default=False)

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False
        )
    )
    updated_at: Optional[datetime] = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now()
        )
    )


class Summoner(SQLModel, table=True):
    __tablename__ = "summoners"

    id: int | None = Field(default=None, primary_key=True)

    puuid: str = Field(index=True, unique=True, nullable=False, max_length=78, min_length=78)
    region: str = Field(nullable=False, min_length=2, max_length=4)

    summoner_name: str = Field(index=True, nullable=False, max_length=64)
    tag_line: str = Field(index=True, nullable=False, max_length=10)

    summoner_level: int = Field(nullable=False)
    profile_icon: int = Field(nullable=False)

    revision_date: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False
        )
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
        )
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now()
        )
    )

    leagues: list["SummonerLeagues"] = Relationship(back_populates="summoner")
    stats: list["MatchParticipant"] = Relationship(back_populates="profile")

    @computed_field
    @property
    def riot_id(self: Self) -> str:
        return f"{self.summoner_name}#{self.tag_line}"


class SummonerLeagues(SQLModel, table=True):
    __tablename__ = "summoner_leagues"

    id: int | None = Field(default=None, primary_key=True)
    summoner_id: int | None = Field(nullable=False, foreign_key="summoners.id")
    league_id: str = Field(index=True, nullable=False)

    queue_type: str = Field(nullable=False)
    tier: str = Field(nullable=False)
    rank: str = Field(nullable=False)

    wins: int = Field(nullable=False)
    losses: int = Field(nullable=False)
    league_points: int = Field(nullable=False)

    summoner: Summoner | None = Relationship(back_populates="leagues")

    @computed_field
    @property
    def total_games(self: Self) -> int:
        return self.wins + self.losses

    @computed_field
    @property
    def win_rate(self: Self) -> float:
        return self.wins / self.total_games * 100


class Match(SQLModel, table=True):
    __tablename__ = "matches"

    id: int | None = Field(default=None, primary_key=True)
    match_id: str = Field(index=True, unique=True, nullable=False)

    platform: str = Field(nullable=False)
    queue_id: int = Field(nullable=False)

    game_mode: str = Field(nullable=False)
    game_type: str = Field(nullable=False)
    game_version: str = Field(nullable=False)

    map_id: int = Field(nullable=False)

    game_start: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    game_end: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True))
    )

    game_duration: int = Field(nullable=False)

    participants: list["MatchParticipant"] = Relationship(back_populates="match")
    teams: list["MatchTeam"] = Relationship(back_populates="match")


class MatchTeam(SQLModel, table=True):
    __tablename__ = "match_teams"

    id: int | None = Field(default=None, primary_key=True)
    match_id: int = Field(nullable=False, foreign_key="matches.id")
    team_id: int = Field(nullable=False)

    bans: list["MatchTeamBans"] = Relationship(back_populates="team")
    objectives: list["MatchTeamObjectives"] = Relationship(back_populates="team")
    win: bool = Field(nullable=False)

    match: Match = Relationship(back_populates="teams")
    participants: list["MatchParticipant"] = Relationship(back_populates="team")


class MatchTeamBans(SQLModel, table=True):
    __tablename__ = "match_team_bans"

    id: int | None = Field(default=None, primary_key=True)
    team_id: int = Field(nullable=False, foreign_key="match_teams.id")

    champion_id: int = Field(nullable=False)
    pick_turn: int = Field(nullable=False)

    team: MatchTeam = Relationship(back_populates="bans")


class MatchTeamObjectives(SQLModel, table=True):
    __tablename__ = "match_team_objectives"

    id: int | None = Field(default=None, primary_key=True)
    team_id: int = Field(nullable=False, foreign_key="match_teams.id")

    objective: str = Field(nullable=False)
    first: bool = Field(default=False)
    kills: int = Field(nullable=False)

    team: MatchTeam = Relationship(back_populates="objectives")


class MatchParticipant(SQLModel, table=True):
    __tablename__ = "match_participants"

    id: int | None = Field(default=None, primary_key=True)
    match_id: int = Field(nullable=False, foreign_key="matches.id")
    team_id: int = Field(nullable=False, foreign_key="match_teams.id")

    summoner_puuid: str = Field(
        nullable=False,
        index=True,
        foreign_key="summoners.puuid"
    )

    champion_id: int = Field(nullable=False)
    champion_name: str = Field(nullable=False)
    lane: str = Field(nullable=False)

    kills: int = Field(nullable=False)
    deaths: int = Field(nullable=False)
    assists: int = Field(nullable=False)
    # kill_participation: float = Field(nullable=False)

    double_kills: int = Field(nullable=False)
    triple_kills: int = Field(nullable=False)
    quadra_kills: int = Field(nullable=False)
    penta_kills: int = Field(nullable=False)
    largest_multi_kill: int = Field(nullable=False)

    damage_dealt_to_champions: int = Field(nullable=False)
    damage_taken: int = Field(nullable=False)

    total_minions_killed: int = Field(nullable=False)
    neutral_minions_killed: int = Field(nullable=False)
    gold_earned: int = Field(nullable=False)

    vision_score: int = Field(nullable=False)
    wards_placed: int = Field(nullable=False)
    wards_killed: int = Field(nullable=False)
    vision_wards_bought: int = Field(nullable=False)

    item0: int | None = Field(nullable=True)
    item1: int | None = Field(nullable=True)
    item2: int | None = Field(nullable=True)
    item3: int | None = Field(nullable=True)
    item4: int | None = Field(nullable=True)
    item5: int | None = Field(nullable=True)
    item6: int | None = Field(nullable=True)

    runes: list["MatchParticipantRunes"] = Relationship(back_populates="participant")
    match: Match = Relationship(back_populates="participants")
    profile: Summoner = Relationship(back_populates="stats")
    team: MatchTeam = Relationship(back_populates="participants")

    @computed_field
    @property
    def kda(self: Self) -> float:
        if self.deaths == 0:
            return round(self.kills + self.assists, 2)

        return round((self.kills + self.assists) / self.deaths, 2)

    @computed_field
    @property
    def total_cs(self: Self) -> int:
        return self.total_minions_killed + self.neutral_minions_killed


class MatchParticipantRunes(SQLModel, table=True):
    __tablename__ = "match_participant_runes"

    id: int | None = Field(default=None, primary_key=True)
    participant_id: int = Field(nullable=False, foreign_key="match_participants.id", index=True)

    primary_style: int = Field(nullable=False, index=True)
    primary_perk0: int = Field(nullable=False)
    primary_perk1: int = Field(nullable=False)
    primary_perk2: int = Field(nullable=False)
    primary_perk3: int = Field(nullable=False)

    secondary_style: int = Field(nullable=False, index=True)
    secondary_perk0: int = Field(nullable=False)
    secondary_perk1: int = Field(nullable=False)

    stat_perk_defense: int = Field(nullable=False)
    stat_perk_flex: int = Field(nullable=False)
    stat_perk_offense: int = Field(nullable=False)

    participant: MatchParticipant | None = Relationship(back_populates="runes")


class SummonerMatchRead(BaseModel):
    summoner_name: str = Field(alias="summoner_name")
    tag_line: str
    riot_id: str


class MatchParticipantRunesRead(BaseModel):
    primary_style: int
    primary_perk0: int
    primary_perk1: int
    primary_perk2: int
    primary_perk3: int

    secondary_style: int
    secondary_perk0: int
    secondary_perk1: int

    stat_perk_defense: int
    stat_perk_flex: int
    stat_perk_offense: int


class MatchParticipantsRead(BaseModel):
    champion_id: int
    champion_name: str
    kills: int
    deaths: int
    assists: int

    kda: float
    total_cs: int
    gold_earned: int
    vision_score: int
    wards_placed: int
    wards_killed: int
    vision_wards_bought: int

    item0: int
    item1: int
    item2: int
    item3: int
    item4: int
    item5: int
    item6: int

    profile: SummonerMatchRead
    runes: list[MatchParticipantRunesRead]


class MatchTeamBansRead(BaseModel):
    champion_id: int
    pick_turn: int


class MatchTeamObjectivesRead(BaseModel):
    objective: str
    first: bool
    kills: int


class MatchTeamsRead(BaseModel):
    team_id: int
    bans: list["MatchTeamBansRead"]
    objectives: list["MatchTeamObjectivesRead"]
    participants: list["MatchParticipantsRead"]
    win: bool


class MatchesRead(BaseModel):
    match_id: str
    platform: str
    queue_id: int
    game_mode: str
    game_type: str
    game_version: str
    map_id: int

    game_start: datetime
    game_end: datetime
    game_duration: int

    teams: list["MatchTeamsRead"]
    # participants: list["MatchParticipantsRead"]


class SummonerLeaguesRead(BaseModel):
    league_id: str
    queue_type: str
    tier: str
    rank: str
    wins: int
    losses: int
    league_points: int
    total_games: int
    win_rate: float


class SummonerSearch(BaseModel):
    puuid: str
    region: str
    summoner_name: str
    tag_line: str
    riot_id: str
    summoner_level: int
    profile_icon: int
    leagues: list[SummonerLeaguesRead]
    revision_date: datetime
    created_at: datetime
    updated_at: datetime


class UserSignUpRequest(BaseModel):
    avatarName: str
    emailAddress: str
    password: str
    password_confirm: str


class UserResponse(BaseModel):
    avatarName: str
    emailAddress: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
