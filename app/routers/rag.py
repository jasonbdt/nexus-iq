from fastapi.routing import APIRouter

from ..internal.db import SessionDep
from ..internal.logging import get_logger

router = APIRouter(
    tags=["RAG"]
)

logger = get_logger(__name__)

@router.post("/ingest/{patch_version}")
def index(patch_version: float):
    return { "message": "It works" }