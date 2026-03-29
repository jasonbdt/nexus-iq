"""Summoner lookup and update endpoints."""
import asyncio
import json
from contextlib import suppress
from typing import Annotated, Optional

from fastapi import status
from fastapi.params import Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.requests import Request
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


@router.get("/search/{tag_line}/{game_name}", response_model=SummonerSearch, response_model_exclude_none=True)
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
    match_count: int = 100
):
    """Update summoner data (ranked stats, match history) by PUUID."""
    logger.info(
        "User[%s] triggered an update for Summoner with PUUID \"%s\"",
        current_user.id, puuid,
    )
def parse_pubsub_message(
    raw_data: bytes | str | dict
) -> tuple[str, dict | str]:
    if isinstance(raw_data, bytes):
        raw_data = raw_data.decode("utf8")

    if isinstance(raw_data, dict):
        obj = raw_data
    elif isinstance(raw_data, str):
        try:
            obj = json.loads(raw_data)
        except json.JSONDecodeError:
            return "update", raw_data
    else:
        return "update", str(raw_data)

    if not isinstance(obj, dict):
        return "update", obj

    event = obj.get("event") or "update"

    if "payload" in obj:
        payload = obj["payload"]
    else:
        payload = {k: v for k, v in obj.items() if k != "event"}

    return event, payload


def build_sse(
    data: dict | str | bytes,
    event: str | None = None,
    event_id: str | None = None,
    retry: int | None = None
) -> str:
    if isinstance(data, bytes):
        data = data.decode('utf8').replace("'", '"')
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    lines = []
    if event:
        lines.append(f"event: {event}")

    if event_id:
        lines.append(f"id: {event_id}")

    if retry is not None:
        lines.append(f"retry: {retry}")

    lines.append(f"data: {payload}")

    return "\n".join(lines) + "\n\n"


@router.get("/subscribe/{puuid}")
async def get_update_status(
    puuid: str,
    redis: RedisDep,
    request: Request
):
    CHANNEL = f"nexus_iq:summoner_profile:{puuid}"

    pubsub = redis.pubsub(ignore_subscribe_messages=True)
    await pubsub.subscribe(CHANNEL)

    async def event_generator():
        try:
            yield build_sse({"status": "connected", "channel": CHANNEL}, event="connected")

            while True:
                if await request.is_disconnected():
                    break

                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )

                if message is not None:
                    if message["type"] == "message":
                        event_name, payload = parse_pubsub_message(message["data"])
                        yield build_sse(payload, event=event_name)
                else:
                    yield ": keepalive\n\n"

                await asyncio.sleep(0.1)
        finally:
            with suppress(Exception):
                await pubsub.unsubscribe(CHANNEL)
                await pubsub.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
