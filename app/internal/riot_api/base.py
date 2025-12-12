from typing import Any, Self, Literal, LiteralString, Awaitable, Optional

import os

import aiohttp
from aiohttp.client_exceptions import ContentTypeError
from fastapi import HTTPException

from ..logging import get_logger

Platform = Literal["americas", "asia", "europe", "sea"]
Region = Literal["br1", "eun1", "euw1", "jp1", "kr", "la1",
"la2", "me1", "na1", "oc1", "ru", "sg2",
"tr1", "tw2", "vn2"]

PlatformOrRegion = Literal[Platform, Region]

logger = get_logger(__name__)


class RiotAPIBase:
    _platform_or_region: PlatformOrRegion = "europe"

    def __init__(self: Self) -> None:
        self._api_base = "https://!!PLATFORM_OR_REGION!!.api.riotgames.com"
        self._api_key = os.getenv("RIOT_API_KEY")

    async def _send_request(self: Self, path: str):
        async with aiohttp.ClientSession() as session:
            headers = {"X-Riot-Token": os.getenv("RIOT_API_KEY")}
            request = session.get(
                url=f"{self._get_api_base()}{path}",
                headers=headers
            )

            async with request as response:
                try:
                    if response.ok:
                        return await response.json()
                except ContentTypeError:
                    raise HTTPException(status_code=500, detail="Internal Error")

                match response.status:
                    case 400:
                        logger.error(f"Bad Request to {path}")
                        raise HTTPException(status_code=400, detail="Bad Request")
                    case 401:
                        logger.error(f"Unauthorized Request to {path}")
                        raise HTTPException(status_code=401, detail="Unauthorized")
                    case 403:
                        logger.error(f"Forbidden Request to {path}")
                        raise HTTPException(status_code=403, detail="Forbidden")
                    case 404:
                        logger.error(f"Data not found at {path}")
                        raise HTTPException(status_code=404, detail="Not Found")
                    case 429:
                        logger.warning(f"Rate limit exceeded at request to {path}")
                        raise HTTPException(status_code=429, detail="Rate limit exceeded")
                    case _:
                        raise HTTPException(status_code=500, detail="Internal Server Error")

    def _get_platform_or_region(self: Self) -> PlatformOrRegion:
        return self._platform_or_region

    def _set_platform_or_region(self: Self, platform_or_region: PlatformOrRegion):
        self._platform_or_region = platform_or_region

    def _get_api_base(self: Self) -> str:
        api_base = self._api_base.replace("!!PLATFORM_OR_REGION!!",
                                          self._get_platform_or_region())

        return api_base
