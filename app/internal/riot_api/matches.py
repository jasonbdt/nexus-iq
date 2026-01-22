from typing import Self

from app.internal.riot_api.base import RiotAPIBase


class RiotMatches(RiotAPIBase):

    async def get_matches(self: Self, puuid: str):
        pass
