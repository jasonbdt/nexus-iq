from fastapi.routing import APIRouter
from starlette.responses import JSONResponse

from ..internal.controllers import patches as PatchNotesController
from ..internal.db import SessionDep
from ..internal.logging import get_logger
from ..internal.services.embeddings import embed_texts
from ..internal.services.vector_store import upsert_vectors

router = APIRouter(
    tags=["RAG"]
)

logger = get_logger(__name__)


@router.post("/ingest/{patch_version}")
async def index(patch_version: float):
    chunks = await PatchNotesController.parse_patch_notes(patch_version)

    if not chunks:
        return JSONResponse(content={
            "message": f"No text extracted from patch notes for {patch_version}"
        }, status_code=400)

    texts = [chunk["text"] for chunk in chunks]
    metadata = [{
        "source": chunk["source"],
        "patch_version": patch_version,
        "chunk_index": chunk["chunk_index"]
    } for chunk in chunks]

    embeddings = embed_texts(texts)
    await upsert_vectors(texts, embeddings, metadata)

    return JSONResponse(content={
        "message": f"Patch Notes for v{patch_version} ingested successfully",
        "count": len(chunks)
    }, status_code=200)
