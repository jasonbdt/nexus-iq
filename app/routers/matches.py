from datetime import datetime, timezone
from typing import Any

from fastapi.routing import APIRouter
from starlette.responses import JSONResponse

from ..internal.controllers import matches as MatchesController
from ..internal.db import SessionDep
from ..internal.logging import get_logger
from ..internal.models import Match, MatchesRead
from ..internal.match_utils import create_match_participant_with_runes
from ..internal.riot_api import RiotAPIDep

router = APIRouter(
    prefix="/matches",
    tags=["Matches"]
)

logger = get_logger(__name__)


@router.get("")
def index():
    return { "message": "It works" }

# TODO: Increase default count value for recent matches
@router.get("/{region}/by-puuid/{puuid}")
async def get_recent_matches_by_puuid(
    region: str,
    puuid: str,
    riot_api: RiotAPIDep,
    session: SessionDep,
    match_count: int = 1
) -> list[MatchesRead]:
    # TODO: Load matches from DB
    # recent_matches = await riot_api.get_recent_matches(puuid, region, count)
    recent_matches = MatchesController.get_recent_matches(puuid, region, match_count, session, riot_api)
    print(recent_matches[0])

    # return JSONResponse(content=recent_matches)

    return recent_matches

    return { "message": "It works" }


def process_match(match_data: dict, session: SessionDep):
    match_info = match_data.get("info", {})
    metadata = match_data.get("metadata", {})

    match = Match(
        match_id=metadata.get("matchId"),
        platform=match_info.get("platformId"),
        queue_id=match_info.get("queueId"),
        game_mode=match_info.get("gameMode"),
        game_type=match_info.get("gameType"),
        game_version=match_info.get("gameVersion"),
        map_id=match_info.get("mapId"),
        game_start=datetime.fromtimestamp(
            match_info.get("gameStartTimestamp", 1) / 1000,
            tz=timezone.utc
        ),
        game_end=datetime.fromtimestamp(
            match_info.get("gameEndTimestamp", 1) / 1000,
            tz=timezone.utc
        ),
        game_duration=match_info.get("gameDuration") if match_info.get("gameEndTimestamp") else match_info.get("gameDuration") / 1000
    )

    session.add(match)
    session.commit()
    session.refresh(match)

    participants_data = match_info.get("participants", [])

    # TODO: Create summoners before creating match participants
    #for participant_data in participants_data:
        #summoner = get_summoner_from_db_by_puuid(participant_data["puuid"], session)
        #if summoner:
        #    handle_existing_summoner(summoner, session)
        #else:
        #    create_or_update_summoner_from_riot(
        #        participant_data["riotIdGameName"],
        #        participant_data["riotIdTagline"],
        #        session
        #    )

    for participant_data in participants_data:
        participant, runes = create_match_participant_with_runes(
            participant_data=participant_data,
            match_id=match.match_id,
            session=session
        )

        session.add(participant)

        if runes:
            session.add(runes)

    #session.commit()
    return match

