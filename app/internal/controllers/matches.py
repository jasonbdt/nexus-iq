from sqlmodel import select

from ..db import SessionDep
from ..logging import get_logger
from ..models import Summoner, Match, MatchParticipant, MatchTeam
from ..riot_api import RiotAPIDep, RiotAPINotFoundError, RiotPlatform, REGION_TO_PLATFORM

logger = get_logger(__name__)

def get_matches(puuid: str, platform: RiotPlatform, match_count: int, session: SessionDep):
    statement = select(Match).join(MatchParticipant).join(MatchTeam).where(
        MatchParticipant.summoner_puuid == puuid,
        # Match.platform == platform.upper()
    ).limit(match_count)

    results = session.exec(statement)
    matches = []
    for match in results:
        matches.append(match)

    return matches

def get_recent_matches(
    puuid: str,
    region: str,
    match_count: int,
    session: SessionDep,
    riot_api: RiotAPIDep
):
    return get_matches(puuid, REGION_TO_PLATFORM[region], match_count, session)