"""Summoner lookup and update endpoints."""

from typing import Annotated, Optional

from fastapi import status
from fastapi.params import Depends
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from ..internal.auth import get_current_active_user, get_current_user_optional
from ..internal.controllers import summoners as SummonersController
from ..internal.db import SessionDep
from ..internal.jobs import enqueue_summoner_update
from ..internal.logging import get_logger
from ..internal.models import SummonerSearch, User
from ..internal.redis import RedisDep
from ..internal.riot_api import RiotAPIDep


router = APIRouter(
    tags=["Summoners"]
)

logger = get_logger(__name__)


@router.get("/search/{tag_line}/{game_name}", response_model=SummonerSearch)
async def get_summoner(
    current_user: Annotated[Optional[User], Depends(get_current_user_optional)],
    tag_line: str,
    game_name: str,
    session: SessionDep,
    riot_api: RiotAPIDep
):
    """Look up a summoner by game name and tag line."""
    if current_user:
        logger.info(
            "User[%s] searching for Summoner \"%s#%s\"",
            current_user.id, game_name, tag_line,
        )
    else:
        logger.info("Anonymous user searching for Summoner \"%s#%s\"", game_name, tag_line)

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
    redis: RedisDep,
    session: SessionDep,
    riot_api: RiotAPIDep,
    match_count: int = 20
):
    """Update summoner data (ranked stats, match history) by PUUID."""
    logger.info(
        "User[%s] triggered an update for Summoner with PUUID \"%s\"",
        current_user.id, puuid,
    )

    new_job = enqueue_summoner_update(redis, puuid, match_count)

    return {"message": "Update queued", "job_details": new_job.data}

    summoner = await SummonersController.find_and_update(
        puuid, session, riot_api, match_count
    )

    if not summoner:
        return JSONResponse(
            content={"message": "Summoner not found"},
            status_code=status.HTTP_404_NOT_FOUND
        )

    return summoner
