from typing import Annotated, Any, Optional
from datetime import datetime, timedelta, timezone

from fastapi import Response, status
from fastapi.params import Depends
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from sqlmodel import select, or_

from .matches import process_match
from ..dependencies import SUMMONER_TTL_MINUTES
from ..internal.auth import get_current_active_user
from ..internal.controllers import summoners as SummonersController
from ..internal.logging import get_logger
from ..internal.db import SessionDep
from ..internal.models import Summoner, SummonerLeagues, SummonerSearch, User

#from ..internal.riot_api.riot_api import RiotAPI
from ..internal.riot_api import (
    RiotAPIFacade,
    RiotAPIDep,
    RiotAPIError,
    riot_exception_to_http,
)


router = APIRouter(
    tags=["Summoners"]
)

logger = get_logger(__name__)


@router.get("/search/{tag_line}/{game_name}", response_model=SummonerSearch)
async def get_summoner(
    current_user: Annotated[User, Depends(get_current_active_user)],
    tag_line: str,
    game_name: str,
    session: SessionDep,
    riot_api: RiotAPIDep
):
    logger.info(
        f"User[{current_user.id}] searching for Summoner \"{game_name}#{tag_line}\"")

    summoner = await SummonersController.find_or_create(
        game_name, tag_line, session, riot_api
    )

    if not summoner:
        return JSONResponse(
            content={"message": "Summoner not found"},
            status_code=status.HTTP_404_NOT_FOUND
        )

    return summoner

@router.patch("/update/{puuid}", response_model=SummonerSearch)
async def update_summoner(
    current_user: Annotated[User, Depends(get_current_active_user)],
    puuid: str,
    session: SessionDep,
    riot_api: RiotAPIDep,
    match_count: int = 20
):
    logger.info(
        f"User[{current_user.id}] triggered an update for Summoner with PUUID \"{puuid}\"")

    summoner = await SummonersController.find_and_update(
        puuid, session, riot_api, match_count
    )

    if not summoner:
        return JSONResponse(
            content={"message": "Summoner not found"},
            status_code=status.HTTP_404_NOT_FOUND
        )

    return summoner
