"""Public HTTP request and response schemas, with no filesystem access."""
from typing import Optional, Self
from datetime import datetime
from pydantic import BaseModel, Field, computed_field, ConfigDict
from app.domain.models import UserRole


class ApiModel(BaseModel):
    """Allow mapping fully loaded application results to HTTP responses."""
    model_config = ConfigDict(from_attributes=True)


class Token(ApiModel):
    """The unchanged OAuth2 token response."""
    access_token: str
    token_type: str


class UpdateQueued(ApiModel):
    """Describe the existing queue acknowledgement accurately."""
    message: str


class SummonerMatchRead(ApiModel):
    """Read schema for summoner identity in match context."""
    summoner_name: str = Field(alias='summoner_name')
    tag_line: str
    riot_id: str


class MatchParticipantRunesRead(ApiModel):
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


class MatchParticipantsRead(ApiModel):
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
        return f'{self.summoner_name}#{self.tag_line}'
    spell_1: Optional[str]
    spell_2: Optional[str]
    primary_style: str
    secondary_style: str


class MatchTeamBansRead(ApiModel):
    """Read schema for a team ban."""
    champion_id: int
    pick_turn: int


class MatchTeamObjectivesRead(ApiModel):
    """Read schema for a team objective."""
    objective: str
    first: bool
    kills: int


class MatchTeamsRead(ApiModel):
    """Read schema for a match team."""
    team_id: int
    bans: list['MatchTeamBansRead']
    objectives: list['MatchTeamObjectivesRead']
    participants: list['MatchParticipantsRead']
    win: bool


class MatchesRead(ApiModel):
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
    teams: list['MatchTeamsRead']


class SummonerLeaguesRead(ApiModel):
    """Read schema for a summoner league entry."""
    queue_type: str
    tier: str
    rank: str
    wins: int
    losses: int
    league_points: int
    total_games: int
    win_rate: float


class SummonerSearch(ApiModel):
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


class UserSignUpRequest(ApiModel):
    """Request schema for user registration."""
    avatarName: str = ''
    emailAddress: str
    password: str
    password_confirm: str
    gameName: str = ''
    tagLine: str = ''


class LinkedSummonerInfo(ApiModel):
    """Schema for a linked summoner account."""
    puuid: str
    riot_id: str
    profile_icon: int
    region: str
    summoner_level: int
    link_slot: int = 0
    link_id: int | None = None
    linked_at: Optional[datetime] = None


class UserResponse(ApiModel):
    """Response schema for user data."""
    avatarName: str
    emailAddress: str
    is_active: bool
    role: UserRole
    created_at: datetime
    updated_at: Optional[datetime]
    linked_summoner: Optional[LinkedSummonerInfo] = None
    summoner_linked_at: Optional[datetime] = None
    additional_summoners: list[LinkedSummonerInfo] = []
    language: str = 'en'
    subscription_tier: str = 'free'


class UserUpdateRequest(ApiModel):
    """Request schema for updating user data."""
    emailAddress: str | None = None
    current_password: str | None = None
    new_password: str | None = None
    language: str | None = None


class LinkSummonerRequest(ApiModel):
    """Request schema for linking a summoner account."""
    gameName: str
    tagLine: str
    link_slot: int = 0


class CoachMessageRead(ApiModel):
    """Read schema for a coaching message."""
    id: int
    role: str
    content: str
    created_at: datetime


class CoachSessionRead(ApiModel):
    """Read schema for a coaching session."""
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[CoachMessageRead] = []


class CoachSessionCreate(ApiModel):
    """Create schema for a new coaching session."""
    title: str = 'New Session'
