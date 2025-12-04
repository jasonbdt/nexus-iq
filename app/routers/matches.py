from fastapi.routing import APIRouter

from ..internal.logging import get_logger

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
