"""RAG endpoints for patch-notes ingestion, querying, and streaming."""

import json

from fastapi.routing import APIRouter
from fastapi.responses import StreamingResponse
from langsmith import uuid7
from starlette.responses import JSONResponse

from ..internal.controllers import patches as PatchNotesController
from ..internal.logging import get_logger
from ..internal.services.embeddings import embed_texts
from ..internal.services.llm import (
    generate_response,
    stream_response,
    determine_patch_versions,
    extract_keywords,
)
from ..internal.services.rag import build_rag_context
from ..internal.services.vector_store import upsert_vectors

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
    """Fetch patch notes, embed chunks, and upsert into the vector store."""
    chunks = await PatchNotesController.parse_patch_notes(patch_version)

    if not chunks:
        return JSONResponse(content={
            "message": f"No text extracted from patch notes for {patch_version}"
        }, status_code=400)

    # Store as float so Qdrant range filters work correctly
    try:
        patch_version_float = float(patch_version)
    except ValueError:
        return JSONResponse(
            content={"message": f"Invalid patch version: {patch_version}"},
            status_code=422,
        )

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

async def _build_context(
    question: str, top_k: int = 15, *, thread_id: str | None = None
) -> str:
    """Build RAG context by embedding the question and searching for similar chunks."""
    patch_versions = determine_patch_versions(question, thread_id=thread_id)
    keywords = extract_keywords(question, thread_id=thread_id)
    return await build_rag_context(question, patch_versions, keywords, top_k=top_k)


@router.post("/query")
async def query_rag(question: str, top_k: int = 5):
    """Query the RAG system about patch notes (full response)."""
    thread_id = str(uuid7())
    context = await _build_context(question, top_k, thread_id=thread_id)
    answer = generate_response(question, context, thread_id=thread_id)
    return JSONResponse(content={"message": answer}, status_code=200)


@router.post("/query/stream")
async def query_rag_stream(question: str, top_k: int = 5):
    """Query the RAG system and stream the response as Server-Sent Events."""
    thread_id = str(uuid7())
    context = await _build_context(question, top_k, thread_id=thread_id)

    def event_generator():
        for delta in stream_response(question, context, thread_id=thread_id):
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
