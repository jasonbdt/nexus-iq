from datetime import datetime, timezone

from fastapi.routing import APIRouter

# from .summoners import get_summoner_from_db_by_puuid, handle_existing_summoner, create_or_update_summoner_from_riot
from ..internal.db import SessionDep
from ..internal.logging import get_logger
from ..internal.models import Match
from ..internal.match_utils import create_match_participant_with_runes

router = APIRouter(
    prefix="/matches",
    tags=["Matches"]
)

logger = get_logger(__name__)


@router.get("")
def index():
    return { "message": "It works" }

@router.get("/by-puuid/{puuid}")
def get_matches_by_puuid(puuid: str):
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

