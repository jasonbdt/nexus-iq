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
    _time_factory = datetime.now()

    id: int | None = Field(default=None, primary_key=True)
    summoner_id: int = Field(nullable=False, foreign_key="summoners.id")
    league_id: str = Field(index=True, nullable=False)

    queue_type: str = Field(nullable=False)
    tier: str = Field(nullable=False)
    rank: str = Field(nullable=False)

    game_wins: int = Field(nullable=False)
    game_losses: int = Field(nullable=False)
    league_points: int = Field(nullable=False)

    summoner: Summoner | None = Relationship(back_populates="leagues")

    @computed_field
    @property
    def total_games(self: Self) -> int:
        return self.game_wins + self.game_losses

    @computed_field
    @property
    def win_rate(self: Self) -> float:
        return self.game_wins / self.total_games * 100


class SummonerLeaguesRead(BaseModel):
    league_id: str
    queue_type: str
    tier: str
    rank: str
    game_wins: int
    game_losses: int
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
