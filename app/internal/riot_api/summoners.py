from typing import Literal, Self, Optional
from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import BaseModel, Field, computed_field, AwareDatetime

from .base import RiotAPIBase, PlatformOrRegion

Game = Literal["lol", "tft"]


class SummonerAccount(BaseModel):
    game_name: str = Field(alias="gameName", serialization_alias="game_name")
    tag_line: str = Field(alias="tagLine", serialization_alias="tag_line")
    puuid: str


class SummonerRegion(BaseModel):
    region: str = Field(serialization_alias="region")


class SummonerLeagues(BaseModel):
    league_id: str = Field(alias="leagueId", serialization_alias="league_id")
    queue_type: str = Field(alias="queueType", serialization_alias="queue_type")

    league_points: int = Field(alias="leaguePoints", serialization_alias="league_points")
    wins: int
    losses: int

    tier: str
    rank: str

    @computed_field
    @property
    def total_games(self: Self) -> int:
        return self.wins + self.losses

    @computed_field
    @property
    def win_rate(self: Self) -> float:
        return self.wins / self.total_games * 100


class Summoner(BaseModel):
    account_info: 'Optional[SummonerAccount]'
    leagues: 'Optional[list[SummonerLeagues]]'
    region: str
    level: int = Field(alias="summonerLevel", serialization_alias="level")
    profile_icon_id: int = Field(alias="profileIconId", serialization_alias="profile_icon")
    revision_date: AwareDatetime = Field(alias="revisionDate", serialization_alias="revision_date")


def _timestamp_to_datetime(timestamp: int) -> datetime:
    return datetime.fromtimestamp(
        tz=timezone.utc,
        timestamp=timestamp / 1000
    )


class RiotSummoners(RiotAPIBase):

    async def get_account(self: Self, game_name: str, tag_line: str) -> SummonerAccount:
        request = await self._send_request(
            path=f"/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
        )

        return SummonerAccount(**request)

    async def get_account_by_puuid(self: Self, puuid: str) -> SummonerAccount:
        request = await self._send_request(
            path=f"/riot/account/v1/accounts/by-puuid/{puuid}"
        )

        return SummonerAccount(**request)

    async def get_active_region(self: Self, game: Game, puuid: str) -> SummonerRegion:
        request = await self._send_request(
            path=f"/riot/account/v1/region/by-game/{game}/by-puuid/{puuid}"
        )

        return SummonerRegion(**request)

    async def get_league_entries(self: Self, puuid: str) -> list[SummonerLeagues]:
        request = await self._send_request(
            path=f"/lol/league/v4/entries/by-puuid/{puuid}"
        )

        return request

    async def get_summoner(
        self: Self,
        puuid: Optional[str] = None,
        tag_line: Optional[str] = None,
        game_name: Optional[str] = None,
    ) -> Summoner:
        if not puuid and game_name and tag_line:
            account_info = await self.get_account(game_name, tag_line)
            puuid = account_info.puuid
        else:
            account_info = await self.get_account_by_puuid(puuid)

        region = await self.get_active_region("lol", puuid)
        self._set_platform_or_region(region.region)

        summoner = await self._send_request(
            path=f"/lol/summoner/v4/summoners/by-puuid/{puuid}"
        )
        summoner["revisionDate"] = _timestamp_to_datetime(summoner["revisionDate"])

        leagues = await self.get_league_entries(puuid)

        return Summoner(
            account_info=account_info,
            leagues=leagues,
            region=region.region,
            **summoner
        )
