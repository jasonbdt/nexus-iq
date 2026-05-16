"""Patch-notes RAG retrieval (shared by LangChain tools / patch subagent)."""

from __future__ import annotations

import asyncio

from app.ai.coach_runtime import coach_request_ctx
from app.ai.config.status_catalog import (
    STEP_DETERMINE_PATCH_RANGE,
    STEP_GENERATE_ANSWER,
    STEP_RESOLVE_CATALOG_PATCH,
    STEP_RETRIEVE_PATCH_NOTES,
    emit_status,
)
from app.ai.utils.history import resolved_question
from app.internal.controllers import patches as PatchNotesController
from app.internal.services.llm import determine_patch_versions, extract_keywords
from app.internal.services.rag import build_rag_context


async def retrieve_patch_notes_context(*, vector_query: str | None = None) -> str:
    """Resolve patch range, embed/search Qdrant, return context string.

    ``vector_query`` overrides the text used for similarity search (subagent tool);
    when omitted, uses the current user message from :data:`coach_request_ctx`.
    Patch version / keyword extraction always uses a history-resolved question.
    """
    rt = coach_request_ctx.get()
    if rt is None:
        raise RuntimeError("coach_request_ctx is not set for patch retrieval")

    writer = rt.writer
    if writer:
        emit_status(writer, STEP_DETERMINE_PATCH_RANGE)

    resolved = resolved_question(rt.user_message, rt.conversation_history)
    thread_id = rt.thread_id
    q_embed = (vector_query or "").strip() or rt.user_message

    if writer:
        emit_status(writer, STEP_RESOLVE_CATALOG_PATCH)
    catalog_latest = await PatchNotesController.get_latest_patch_version_float()

    patch_versions = await asyncio.to_thread(
        determine_patch_versions,
        resolved,
        catalog_latest_patch=catalog_latest,
        thread_id=thread_id,
    )
    keywords = await asyncio.to_thread(
        extract_keywords,
        resolved,
        thread_id=thread_id,
    )

    if writer:
        emit_status(writer, STEP_RETRIEVE_PATCH_NOTES)
    top_k = rt.top_k
    ctx = await build_rag_context(
        q_embed,
        patch_versions,
        keywords,
        top_k=top_k,
    )
    if writer:
        emit_status(writer, STEP_GENERATE_ANSWER)
        rt.generate_answer_status_emitted = True
    return ctx
