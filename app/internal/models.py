"""SQLModel and Pydantic models for the application domain."""
# pylint: disable=duplicate-code
import json

from typing import Optional, Self
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, UniqueConstraint
from sqlalchemy.sql.functions import now as server_now
from sqlmodel import Column, Field, Relationship, SQLModel
from pydantic import BaseModel, computed_field

from .ddragon_config import ddragon_data_path


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    """Enumeration of user permission roles."""

    ADMINISTRATOR = "administrator"
    MODERATOR = "moderator"
    PAID_MEMBER = "paid_member"
    MEMBER = "member"


class UserSummonerLink(SQLModel, table=True):
    """Junction table (2NF) linking users to their League of Legends summoner accounts.
    link_slot: 0 = primary (required at registration), 1–2 = additional (Premium only).
    """
    __tablename__ = "user_summoner_links"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(nullable=False, foreign_key="users.id", index=True)
    link_slot: int = Field(nullable=False, index=True)  # 0=primary, 1–2=additional
    summoner_puuid: str = Field(nullable=False, foreign_key="summoners.puuid")
    linked_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=server_now(),
            nullable=False,
        ),
    )

    user: Optional["User"] = Relationship(back_populates="summoner_links")
    summoner: Optional["Summoner"] = Relationship(back_populates="user_links")

    __table_args__ = (UniqueConstraint("user_id", "link_slot", name="uq_user_summoner_link_slot"),)


class Role(SQLModel, table=True):
    """Table storing role definitions."""
    __tablename__ = "roles"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, nullable=False, index=True, max_length=32)

    user_links: list["UserRoleLink"] = Relationship(back_populates="role")


class UserRoleLink(SQLModel, table=True):
    """Junction table (2NF) linking users to roles."""
    __tablename__ = "user_roles"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(nullable=False, foreign_key="users.id", unique=True, index=True)
    role_id: int = Field(nullable=False, foreign_key="roles.id", index=True)
    assigned_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=server_now(),
            nullable=False,
        ),
    )

    user: Optional["User"] = Relationship(back_populates="role_links")
    role: Optional["Role"] = Relationship(back_populates="user_links")


class User(SQLModel, table=True):
    """ORM model for the users table."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    avatarName: str = Field(index=True, nullable=False)
    emailAddress: str = Field(unique=True, nullable=False)
    password: str = Field(nullable=False)
    is_active: bool = Field(default=False)
    language: str = Field(default="en", max_length=10)
    subscription_tier: str = Field(default="free", max_length=32)  # free, premium, etc.

    summoner_links: list["UserSummonerLink"] = Relationship(back_populates="user")
    role_links: list["UserRoleLink"] = Relationship(back_populates="user")

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=server_now(),
            nullable=False
        )
    )
    updated_at: Optional[datetime] = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=server_now(),
            onupdate=server_now()
        )
    )


class Summoner(SQLModel, table=True):
    """ORM model for the summoners table."""

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
            server_default=server_now(),
        )
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=server_now(),
            onupdate=server_now()
        )
    )

    leagues: list["SummonerLeagues"] = Relationship(back_populates="summoner")
    user_links: list["UserSummonerLink"] = Relationship(back_populates="summoner")

    @computed_field
    @property
    def riot_id(self: Self) -> str:
        """Return Riot ID as name#tag."""
        return f"{self.summoner_name}#{self.tag_line}"


class SummonerLeagues(SQLModel, table=True):
    """ORM model for per-summoner league entries."""

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
        """Return total games played."""
        return self.wins + self.losses

    @computed_field
    @property
    def win_rate(self: Self) -> float:
        """Return win rate as a percentage."""
        return self.wins / self.total_games * 100


class Match(SQLModel, table=True):
    """ORM model for the matches table."""

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
    """ORM model for a team within a match."""

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
    """ORM model for champion bans within a team."""

    __tablename__ = "match_team_bans"

    id: int | None = Field(default=None, primary_key=True)
    team_id: int = Field(nullable=False, foreign_key="match_teams.id")

    champion_id: int = Field(nullable=False)
    pick_turn: int = Field(nullable=False)

    team: MatchTeam = Relationship(back_populates="bans")


class MatchTeamObjectives(SQLModel, table=True):
    """ORM model for team objectives within a match."""

    __tablename__ = "match_team_objectives"

    id: int | None = Field(default=None, primary_key=True)
    team_id: int = Field(nullable=False, foreign_key="match_teams.id")

    objective: str = Field(nullable=False)
    first: bool = Field(default=False)
    kills: int = Field(nullable=False)

    team: MatchTeam = Relationship(back_populates="objectives")


class MatchParticipant(SQLModel, table=True):
    """ORM model for a participant within a match."""

    __tablename__ = "match_participants"

    id: int | None = Field(default=None, primary_key=True)
    match_id: int = Field(nullable=False, foreign_key="matches.id")
    team_id: int = Field(nullable=False, foreign_key="match_teams.id")

    summoner_puuid: str = Field(
        nullable=False,
        index=True
    )

    summoner_name: str = Field(nullable=False)
    tag_line: str = Field(nullable=False)

    champion_id: int = Field(nullable=False)
    champion_name: str = Field(nullable=False)
    champion_level: int = Field(nullable=False)
    lane: str = Field(nullable=False)

    summoner_spell_1: int = Field(nullable=False)
    summoner_spell_2: int = Field(nullable=False)

    kills: int = Field(nullable=False)
    deaths: int = Field(nullable=False)
    assists: int = Field(nullable=False)

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
    team: MatchTeam = Relationship(back_populates="participants")

    @computed_field
    @property
    def kda(self: Self) -> float:
        """Calculate KDA ratio."""
        if self.deaths == 0:
            return round(self.kills + self.assists, 2)

        return round((self.kills + self.assists) / self.deaths, 2)

    @computed_field
    @property
    def total_cs(self: Self) -> int:
        """Return total creep score."""
        return self.total_minions_killed + self.neutral_minions_killed


class MatchParticipantRunes(SQLModel, table=True):
    """ORM model for rune selections of a match participant."""

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
    """Read schema for summoner identity in match context."""

    summoner_name: str = Field(alias="summoner_name")
    tag_line: str
    riot_id: str


class MatchParticipantRunesRead(BaseModel):
    """Read schema for participant rune selections."""

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


def find_entry_by_key(data: dict, wanted_key: int | str):
    wanted_key = str(wanted_key)

    return next(
        (
            entry
            for entry in data.get("data", {}).values()
            if entry.get("key") == wanted_key
        ),
        None
    )


def find_rune_by_id(data: dict, wanted_key: int):
    return next(
        (
            entry for entry in data
            if entry.get("id") == wanted_key
        )
    )

class MatchParticipantsRead(BaseModel):
    """Read schema for a match participant."""

    champion_id: int
    champion_name: str
    champion_level: int
    summoner_name: str
    summoner_puuid: str
    lane: str
    tag_line: str
    kills: int
    deaths: int
    assists: int

    summoner_spell_1: int = Field(exclude=True)
    summoner_spell_2: int = Field(exclude=True)

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

    runes: list[MatchParticipantRunesRead] = Field(exclude=True)

    @computed_field
    @property
    def riot_id(self: Self) -> str:
        """Get the full RiotID of the match participant."""
        return f"{self.summoner_name}#{self.tag_line}"

    @computed_field
    @property
    def spell_1(self: Self) -> Optional[str]:
        with open(ddragon_data_path("en_US/summoner.json"), encoding="utf-8") as file_obj:
            data = json.load(file_obj)
            entry = find_entry_by_key(data, self.summoner_spell_1)
            file_obj.close()

            return entry.get('id', None)

    @computed_field
    @property
    def spell_2(self: Self) -> Optional[str]:
        with open(ddragon_data_path("en_US/summoner.json"), encoding="utf-8") as file_obj:
            data = json.load(file_obj)
            entry = find_entry_by_key(data, self.summoner_spell_2)
            file_obj.close()
            return entry.get('id', None)

    @computed_field
    @property
    def primary_style(self: Self) -> str:
        with open(ddragon_data_path("en_US/runesReforged.json"), encoding="utf-8") as file_obj:
            data = json.load(file_obj)
            entry = find_rune_by_id(data, self.runes[0].primary_style)
            file_obj.close()
            return entry.get("icon", None)

    @computed_field
    @property
    def secondary_style(self: Self) -> str:
        with open(ddragon_data_path("en_US/runesReforged.json"), encoding="utf-8") as file_obj:
            data = json.load(file_obj)
            entry = find_rune_by_id(data, self.runes[0].secondary_style)
            file_obj.close()
            return entry.get("icon", None)


class MatchTeamBansRead(BaseModel):
    """Read schema for a team ban."""

    champion_id: int
    pick_turn: int


class MatchTeamObjectivesRead(BaseModel):
    """Read schema for a team objective."""

    objective: str
    first: bool
    kills: int


class MatchTeamsRead(BaseModel):
    """Read schema for a match team."""

    team_id: int
    bans: list["MatchTeamBansRead"]
    objectives: list["MatchTeamObjectivesRead"]
    participants: list["MatchParticipantsRead"]
    win: bool


class MatchesRead(BaseModel):
    """Read schema for a match."""

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


class SummonerLeaguesRead(BaseModel):
    """Read schema for a summoner league entry."""

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
    """Read schema for summoner search results."""
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
    status: str
    update_progress: Optional[float]


class UserSignUpRequest(BaseModel):
    """Request schema for user registration."""

    avatarName: str = ""
    emailAddress: str
    password: str
    password_confirm: str
    # Required: link primary player account during registration
    gameName: str = ""
    tagLine: str = ""


class LinkedSummonerInfo(BaseModel):
    """Schema for a linked summoner account."""

    puuid: str
    riot_id: str
    profile_icon: int
    region: str
    summoner_level: int
    link_slot: int = 0  # 0=primary, 1-2=additional
    link_id: int | None = None  # for DELETE additional
    linked_at: Optional[datetime] = None


class UserResponse(BaseModel):
    """Response schema for user data."""

    avatarName: str
    emailAddress: str
    is_active: bool
    role: UserRole
    created_at: datetime
    updated_at: Optional[datetime]
    linked_summoner: Optional[LinkedSummonerInfo] = None
    summoner_linked_at: Optional[datetime] = None
    additional_summoners: list[LinkedSummonerInfo] = []  # Premium: slots 1-2
    language: str = "en"
    subscription_tier: str = "free"


class UserUpdateRequest(BaseModel):
    """Request schema for updating user data."""

    emailAddress: str | None = None
    current_password: str | None = None
    new_password: str | None = None
    language: str | None = None


class LinkSummonerRequest(BaseModel):
    """Request schema for linking a summoner account."""

    gameName: str
    tagLine: str
    link_slot: int = 0  # 0=primary, 1-2=additional (Premium only)


# ── Coach / Chat ──────────────────────────────────────────────────────────────

class CoachSession(SQLModel, table=True):
    """ORM model for a coaching chat session."""

    __tablename__ = "coach_sessions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(nullable=False, foreign_key="users.id", index=True)
    title: str = Field(nullable=False, default="New Session", max_length=200)
    langsmith_thread_id: str | None = Field(
        default=None,
        max_length=36,
        nullable=True,
        description="UUID v7 string for LangSmith thread grouping",
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), server_default=server_now(), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=server_now(),
            onupdate=server_now(),
        ),
    )

    messages: list["CoachMessage"] = Relationship(back_populates="session")


class CoachMessage(SQLModel, table=True):
    """ORM model for a message within a coaching session."""

    __tablename__ = "coach_messages"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(nullable=False, foreign_key="coach_sessions.id", index=True)
    role: str = Field(nullable=False)          # "user" | "assistant"
    content: str = Field(nullable=False)
    thought_seconds: int | None = Field(
        default=None,
        nullable=True,
        description="Seconds until first output token, or full stream if none.",
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), server_default=server_now(), nullable=False),
    )

    session: CoachSession | None = Relationship(back_populates="messages")


class CoachMessageRead(BaseModel):
    """Read schema for a coaching message."""

    id: int
    role: str
    content: str
    created_at: datetime
    thought_seconds: int | None = None


class CoachSessionRead(BaseModel):
    """Read schema for a coaching session."""

    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[CoachMessageRead] = []


class CoachSessionCreate(BaseModel):
    """Create schema for a new coaching session."""

    title: str = "New Session"
