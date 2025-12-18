from typing import Optional, Self
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
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

    @computed_field
    @property
    def riot_id(self: Self) -> str:
        return f"{self.summoner_name}#{self.tag_line}"


class SummonerLeagues(SQLModel, table=True):
    __tablename__ = "summoner_leagues"

    id: int | None = Field(default=None, primary_key=True)
    summoner_id: int = Field(nullable=False, foreign_key="summoners.id")
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


class MatchParticipant(SQLModel, table=True):
    __tablename__ = "match_participants"

    id: int | None = Field(default=None, primary_key=True)
    match_id: str = Field(nullable=False, foreign_key="matches.match_id")
    team_id: int = Field(nullable=False)

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
    kill_participation: float = Field(nullable=False)

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
