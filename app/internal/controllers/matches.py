"""Controller for retrieving match data from the database."""

from sqlmodel import select
from sqlalchemy import desc

from ..db import SessionDep
from ..logging import get_logger
from ..models import Match, MatchParticipant, MatchTeam
from ..riot_api import RiotAPIDep, RiotPlatform, REGION_TO_PLATFORM

logger = get_logger(__name__)


def get_match_by_id(match_id: str, session: SessionDep) -> Match | None:
    """Return a single match by its Riot match ID, or None if not found."""
    statement = select(Match).where(Match.match_id == match_id)
    return session.exec(statement).first()


def get_matches(puuid: str, _platform: RiotPlatform, match_count: int, session: SessionDep):
    """Return stored matches for a player from the database."""
    statement = select(Match).join(MatchParticipant).join(MatchTeam).where(
        MatchParticipant.summoner_puuid == puuid,
    ).limit(match_count).order_by(desc('game_end'))

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
    _riot_api: RiotAPIDep
):
    """Return recent matches for a player, delegating to get_matches."""
    return get_matches(puuid, REGION_TO_PLATFORM[region], match_count, session)
