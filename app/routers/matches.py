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
