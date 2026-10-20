"""Infrastructure-independent entities and aggregate-owned values."""
# Data records preserve all stored fields; API spelling is retained at the mapper boundary.
# pylint: disable=too-many-instance-attributes,invalid-name,duplicate-code
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Self


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    """Enumeration of user permission roles."""

    ADMINISTRATOR = "administrator"
    MODERATOR = "moderator"
    PAID_MEMBER = "paid_member"
    MEMBER = "member"


@dataclass(kw_only=True)
class UserSummonerLink:
    """UserSummonerLink entity."""

    id: int | None = None
    user_id: int | None = None
    link_slot: int
    summoner_puuid: str
    linked_at: datetime = field(default_factory=utc_now)


@dataclass(kw_only=True)
class User:
    """User entity."""

    id: int | None = None
    avatarName: str
    emailAddress: str
    password: str
    is_active: bool = False
    language: str = 'en'
    subscription_tier: str = 'free'
    summoner_links: list['UserSummonerLink'] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: Optional[datetime] = field(default_factory=utc_now)
    role: UserRole = UserRole.MEMBER


@dataclass(kw_only=True)
class Summoner:
    """Summoner entity."""

    id: int | None = None
    puuid: str
    region: str
    summoner_name: str
    tag_line: str
    summoner_level: int
    profile_icon: int
    revision_date: datetime
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    leagues: list['SummonerLeagues'] = field(default_factory=list)

    @property
    def riot_id(self: Self) -> str:
        """Return Riot ID as name#tag."""
        return f"{self.summoner_name}#{self.tag_line}"


@dataclass(kw_only=True)
class SummonerLeagues:
    """SummonerLeagues entity."""

    id: int | None = None
    summoner_id: int | None = None
    queue_type: str
    tier: str
    rank: str
    wins: int
    losses: int
    league_points: int

    @property
    def total_games(self: Self) -> int:
        """Return total games played."""
        return self.wins + self.losses

    @property
    def win_rate(self: Self) -> float:
        """Return win rate as a percentage."""
        return self.wins / self.total_games * 100


@dataclass(kw_only=True)
class Match:
    """Match entity."""

    id: int | None = None
    match_id: str
    platform: str
    queue_id: int
    game_mode: str
    game_type: str
    game_version: str
    map_id: int
    game_start: datetime
    game_end: Optional[datetime]
    game_duration: int
    teams: list['MatchTeam'] = field(default_factory=list)


@dataclass(kw_only=True)
class MatchTeam:
    """MatchTeam entity."""

    id: int | None = None
    match_id: int | None = None
    team_id: int
    bans: list['MatchTeamBans'] = field(default_factory=list)
    objectives: list['MatchTeamObjectives'] = field(default_factory=list)
    win: bool
    participants: list['MatchParticipant'] = field(default_factory=list)


@dataclass(kw_only=True)
class MatchTeamBans:
    """MatchTeamBans entity."""

    id: int | None = None
    team_id: int | None = None
    champion_id: int
    pick_turn: int


@dataclass(kw_only=True)
class MatchTeamObjectives:
    """MatchTeamObjectives entity."""

    id: int | None = None
    team_id: int | None = None
    objective: str
    first: bool = False
    kills: int


@dataclass(kw_only=True)
class MatchParticipant:
    """MatchParticipant entity."""

    id: int | None = None
    match_id: int | None = None
    team_id: int | None = None
    summoner_puuid: str
    summoner_name: str
    tag_line: str
    champion_id: int
    champion_name: str
    champion_level: int
    lane: str
    summoner_spell_1: int
    summoner_spell_2: int
    kills: int
    deaths: int
    assists: int
    double_kills: int
    triple_kills: int
    quadra_kills: int
    penta_kills: int
    largest_multi_kill: int
    damage_dealt_to_champions: int
    damage_taken: int
    total_minions_killed: int
    neutral_minions_killed: int
    gold_earned: int
    vision_score: int
    wards_placed: int
    wards_killed: int
    vision_wards_bought: int
    item0: int | None
    item1: int | None
    item2: int | None
    item3: int | None
    item4: int | None
    item5: int | None
    item6: int | None
    runes: list['MatchParticipantRunes'] = field(default_factory=list)

    @property
    def kda(self: Self) -> float:
        """Calculate KDA ratio."""
        if self.deaths == 0:
            return round(self.kills + self.assists, 2)

        return round((self.kills + self.assists) / self.deaths, 2)

    @property
    def total_cs(self: Self) -> int:
        """Return total creep score."""
        return self.total_minions_killed + self.neutral_minions_killed


@dataclass(kw_only=True)
class MatchParticipantRunes:
    """MatchParticipantRunes entity."""

    id: int | None = None
    participant_id: int | None = None
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


@dataclass(kw_only=True)
class CoachSession:
    """CoachSession entity."""

    id: int | None = None
    user_id: int
    title: str = 'New Session'
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    messages: list['CoachMessage'] = field(default_factory=list)


@dataclass(kw_only=True)
class CoachMessage:
    """CoachMessage entity."""

    id: int | None = None
    session_id: int
    role: str
    content: str
    created_at: datetime = field(default_factory=utc_now)
