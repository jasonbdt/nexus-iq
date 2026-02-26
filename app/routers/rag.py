import json

from fastapi.routing import APIRouter
from fastapi.responses import StreamingResponse
from starlette.responses import JSONResponse

from ..internal.controllers import patches as PatchNotesController
from ..internal.db import SessionDep
from ..internal.logging import get_logger
from ..internal.services.embeddings import embed_text, embed_texts
from ..internal.services.llm import generate_response, stream_response, determine_patch_versions, extract_keywords
from ..internal.services.vector_store import upsert_vectors, search_similar

router = APIRouter(
    tags=["RAG"]
)

logger = get_logger(__name__)


@router.get("/patches")
async def list_patches():
    """Return all patch versions available on the LoL patch-notes listing page."""
    patches = await PatchNotesController.list_available_patches()
    return JSONResponse(content={"patches": patches}, status_code=200)


@router.post("/ingest/{patch_version}")
async def index(patch_version: str):
    chunks = await PatchNotesController.parse_patch_notes(patch_version)

    if not chunks:
        return JSONResponse(content={
            "message": f"No text extracted from patch notes for {patch_version}"
        }, status_code=400)

    # Store as float so Qdrant range filters work correctly
    try:
        patch_version_float = float(patch_version)
    except ValueError:
        return JSONResponse(content={"message": f"Invalid patch version: {patch_version}"}, status_code=422)

    texts = [chunk["text"] for chunk in chunks]
    metadata = [{
        "source": chunk["source"],
        "patch_version": patch_version_float,
        "chunk_index": chunk["chunk_index"]
    } for chunk in chunks]

    embeddings = embed_texts(texts)
    await upsert_vectors(texts, embeddings, metadata)

    return JSONResponse(content={
        "message": f"Patch Notes for v{patch_version} ingested successfully",
        "count": len(chunks)
    }, status_code=200)

async def _build_context(question: str, top_k: int = 15) -> str:
    patch_versions = determine_patch_versions(question)
    keywords = extract_keywords(question)
    query_embedding = await embed_text(question)
    results = await search_similar(
        query_embedding, patch_versions, top_k=top_k, keywords=keywords or None
    )
    parts = [
        f"[Patch {r['patch_version']}]\n{r['text']}"
        for r in results
    ]
    return "\n\n---\n\n".join(parts)


@router.post("/query")
async def query_rag(question: str, top_k: int = 5):
    """Query the RAG system about patch notes (full response)."""
    context = await _build_context(question, top_k)
    answer = generate_response(question, context)
    return JSONResponse(content={"message": answer}, status_code=200)


@router.post("/query/stream")
async def query_rag_stream(question: str, top_k: int = 5):
    """Query the RAG system and stream the response as Server-Sent Events."""
    context = await _build_context(question, top_k)

    def event_generator():
        for delta in stream_response(question, context):
            # Each SSE message: data: <json>\n\n
            yield f"data: {json.dumps({'delta': delta})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
