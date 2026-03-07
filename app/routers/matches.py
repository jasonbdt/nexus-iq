"""Match history endpoints for League of Legends."""

from fastapi import HTTPException
from fastapi.routing import APIRouter

from ..internal.controllers import matches as MatchesController
from ..internal.db import SessionDep
from ..internal.logging import get_logger
from ..internal.models import MatchesRead
from ..internal.riot_api import RiotAPIDep

router = APIRouter(
    prefix="/matches",
    tags=["Matches"]
)

logger = get_logger(__name__)


@router.get("")
def index():
    """Health check for the matches API."""
    return { "message": "It works" }


@router.get("/{region}/by-id/{match_id}", response_model=MatchesRead)
def get_match_by_id(
    match_id: str,
    session: SessionDep
) -> MatchesRead:
    """Return a single match by region and Riot match ID."""
    match = MatchesController.get_match_by_id(match_id, session)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


@router.get("/{region}/by-puuid/{puuid}")
async def get_recent_matches_by_puuid(
    region: str,
    puuid: str,
    riot_api: RiotAPIDep,
    session: SessionDep,
    match_count: int = 10
) -> list[MatchesRead]:
    """Return recent match history for a player by region and PUUID."""
    return MatchesController.get_recent_matches(
        puuid, region, match_count, session, riot_api
    )
