from typing import Self, Optional
from datetime import datetime, timezone

import requests
from fastapi.exceptions import HTTPException

from app.dependencies import RIOT_API_KEY
from ..logging import get_logger

logger = get_logger(__name__)


class RiotAPI:
    _platform_or_region: str
    _api_base: str = "https://!!PLATFORM_OR_REGION!!.api.riotgames.com"
    _api_key: str = RIOT_API_KEY

    def __init__(self: Self):
        logger.info("RiotAPI initialized successfully")


    def get_summoner(
        self: Self,
        player_name: str,
        tag_line: str
    ) -> Optional[dict]:
        summoner_puuid, player_name, tag_line = self._get_account_by_riot_id(
            player_name=player_name,
            tag_line=tag_line
        )

        if summoner_puuid:
            summoner_region = self._get_region_by_puuid("lol", summoner_puuid)

            if summoner_region:
                summoner_info = self._get_summoner_info_by_puuid(
                    region=summoner_region,
                    puuid=summoner_puuid
                )

                return {
                    "puuid": summoner_puuid,
                    "region": summoner_region,
                    "summonerName": player_name,
                    "tagLine": tag_line,
                    "summonerLevel": summoner_info.get("summonerLevel"),
                    "profileIcon": summoner_info.get("profileIcon"),
                    "revisionDate": datetime.fromtimestamp(
                        timestamp=summoner_info.get("revisionDate") / 1000,
                        tz=timezone.utc
                    ),
                }
            else:
                raise HTTPException(status_code=500, detail="Internal Error")
        else:
            raise HTTPException(status_code=404, detail="Summoner not found")


    def get_summoner_by_puuid(self: Self, puuid: str) -> Optional[dict]:
        summoner_region = self._get_region_by_puuid("lol", puuid)
        summoner_info = self._get_summoner_info_by_puuid(summoner_region, puuid)

        if summoner_region and summoner_info:
            return {
                "puuid": puuid,
                "region": summoner_region,
                "summonerName": summoner_info.get("summonerName"),
                "tagLine": summoner_info.get("tagLine"),
                "summonerLevel": summoner_info.get("summonerLevel"),
                "profileIcon": summoner_info.get("profileIcon"),
                "revisionDate": datetime.fromtimestamp(
                    timestamp=summoner_info.get("revisionDate") / 1000,
                    tz=timezone.utc
                ),
            }

        return None


    def get_summoner_leagues(self: Self, region: str, puuid: str) -> Optional[list[dict]]:
        self._set_platform_or_region(region)
        response = requests.get(
            f"{self._get_api_base()}/lol/league/v4/entries/by-puuid/"
            f"{puuid}",
            headers={
                "X-Riot-Token": self._api_key
            }
        )

        if response.ok:
            try:
                data = response.json()
                return [{
                    "league_id": league.get("leagueId"),
                    "queue_type": league.get("queueType"),
                    "tier": league.get("tier"),
                    "rank": league.get("rank"),
                    "game_wins": league.get("wins"),
                    "game_losses": league.get("losses"),
                    "league_points": league.get("leaguePoints"),
                } for league in data]
            except requests.exceptions.JSONDecodeError:
                raise HTTPException(status_code=500, detail="Internal Error")

        return None


    def _get_account_by_riot_id(
        self: Self,
        player_name: str,
        tag_line: str
    ) -> Optional[tuple[str, str, str]]:
        self._set_platform_or_region("europe")
        response = requests.get(
            f"{self._get_api_base()}/riot/account/v1/accounts/by-riot-id/"
            f"{player_name}/{tag_line.upper()}",
            headers={
                "X-Riot-Token": self._api_key
            },
        )

        if response.ok:
            data = response.json()
            return data.get("puuid"), data.get("gameName"), data.get("tagLine")

        match response.status_code:
            case 401:
                logger.debug("Call to Riot was unauthorized")
                raise HTTPException(status_code=500, detail="Internal Server Error")
            case 404:
                logger.debug("Summoner doesn't exist at Riot")
                raise HTTPException(status_code=404, detail="Summoner not found")
            case 429:
                logger.debug("Riot API Key expired, please regenerate the key")
                raise HTTPException(status_code=500, detail="Internal Server Error")

        return None


    def _get_region_by_puuid(
        self: Self,
        game_name: str,
        puuid: str
    ) -> Optional[str]:
        self._set_platform_or_region("europe")
        response = requests.get(
            f"{self._get_api_base()}/riot/account/v1/region/by-game/"
            f"{game_name}/by-puuid/{puuid}",
            headers={
                "X-Riot-Token": self._api_key
            }
        )

        if response.ok:
            try:
                data = response.json()
                return data.get("region")
            except requests.exceptions.JSONDecodeError:
                raise HTTPException(status_code=500, detail="Internal Error")

        return None


    def _get_summoner_info_by_puuid(self: Self, region: str, puuid: str) -> Optional[dict]:
        self._set_platform_or_region(region)
        response = requests.get(
            f"{self._get_api_base()}/lol/summoner/v4/summoners/by-puuid/"
            f"{puuid}",
            headers={
                "X-Riot-Token": self._api_key
            }
        )

        if response.ok:
            try:
                data = response.json()
                return {
                    "profileIcon": data.get("profileIconId"),
                    "revisionDate": data.get("revisionDate"),
                    "summonerLevel": data.get("summonerLevel")
                }
            except requests.exceptions.JSONDecodeError:
                raise HTTPException(status_code=500, detail="Internal Error")

        return None


    def _set_platform_or_region(self: Self, platform_or_region: str) -> None:
        self._platform_or_region = platform_or_region


    def _get_platform_or_region(self: Self) -> str:
        return self._platform_or_region


    def _get_api_base(self: Self) -> str:
        api_base = self._api_base.replace("!!PLATFORM_OR_REGION!!",
                                          self._get_platform_or_region())

        return api_base


    def get_match_history(
        self: Self,
        puuid: str,
        start: int = 0,
        count: int = 20
    ):
        region = self._get_region_by_puuid("lol", puuid)
        if not region:
            logger.error(f"Could not determine region for PUUID: {puuid}")
            return None

        self._set_platform_or_region("europe")

        url = f"{self._get_api_base()}/lol/match/v5/matches/by-puuid/{puuid}/ids"
        params = {
            "start": start,
            "count": min(count, 100)
        }

        response = requests.get(
            url,
            headers={
                "X-Riot-Token": self._api_key
            },
            params=params
        )

        if response.ok:
            try:
                return response.json()
            except requests.exceptions.JSONDecodeError:
                logger.error("Failed to decode match history response")
                raise HTTPException(status_code=500, detail="Internal Error")

        match response.status_code:
            case 400:
                logger.error("Bad request for match history")
                raise HTTPException(status_code=400, detail="Invalid request parameters")
            case 401:
                logger.error("Unauthorized match history request")
                raise HTTPException(status_code=500, detail="Internal Server Error")
            case 403:
                logger.error("Forbidden match history request")
                raise HTTPException(status_code=500, detail="Internal Server Error")
            case 429:
                logger.warning("Rate limit exceeded for match history")
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            case _:
                logger.error(f"Unexpected error fetching match history: {response.status_code}")
                raise HTTPException(status_code=500, detail="Internal Server Error")


    def get_match_by_id(
        self: Self,
        match_id: str,
        puuid: Optional[str] = None
    ):
        if "_" in match_id:
            platform = match_id.split("_")[0].lower()
            # Map platform to regional routing
            platform_to_region = {
                "euw1": "europe", "eun1": "europe", "tr1": "europe", "ru": "europe",
                "na1": "americas", "br1": "americas", "la1": "americas", "la2": "americas",
                "kr": "asia", "jp1": "asia", "oc1": "asia", "ph2": "asia", "sg2": "asia", "th2": "asia", "tw2": "asia",
                "vn2": "asia"
            }
            regional_routing = platform_to_region.get(platform, "europe")
        elif puuid:
            # Fallback: determine region from PUUID
            region = self._get_region_by_puuid("lol", puuid)
            if region:
                region_mapping = {
                    "europe": "europe",
                    "americas": "americas",
                    "asia": "asia"
                }
                regional_routing = region_mapping.get(region.lower(), "europe")
            else:
                regional_routing = "europe"
        else:
            # Default to europe if we can't determine
            regional_routing = "europe"

        self._set_platform_or_region(regional_routing)

        response = requests.get(
            f"{self._get_api_base()}/lol/match/v5/matches/{match_id}",
            headers={"X-Riot-Token": self._api_key}
        )

        if response.ok:
            try:
                return response.json()
            except requests.exceptions.JSONDecodeError:
                logger.error("Failed to decode match data response")
                raise HTTPException(status_code=500, detail="Internal Error")

        match response.status_code:
            case 404:
                logger.warning(f"Match not found: {match_id}")
                return None
            case 401:
                logger.error("Unauthorized match request")
                raise HTTPException(status_code=500, detail="Internal Server Error")
            case 403:
                logger.error("Forbidden match request")
                raise HTTPException(status_code=500, detail="Internal Server Error")
            case 429:
                logger.warning("Rate limit exceeded for match data")
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            case _:
                logger.error(f"Unexpected error fetching match: {response.status_code}")
                raise HTTPException(status_code=500, detail="Internal Server Error")
