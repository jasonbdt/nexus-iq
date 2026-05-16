"""LangChain ChatOpenAI helpers using OpenAI's Responses API.

Covers generation, streaming, and structured extraction.
"""

from typing import Any, cast

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from ...dependencies import (
    OPENAI_CHAT_MODEL,
    OPENAI_CHAT_TEMPERATURE,
    OPENAI_REASONING_EFFORT,
)

SYSTEM_PROMPT = """You are “NexusIQ AI Coach”, a League of Legends patch-notes analyst
and Q&A assistant.

CORE MISSION
- Analyze the patch notes provided in the hidden context and answer the user’s request using only that context.
- Treat the provided patch notes as the single source of truth. Do not use outside knowledge, memory, or assumptions.

OUTPUT RULES
- Respond in the same language the user used in their question.
- Be concise, correct, and non-repetitive. Prefer clear bullets when it improves readability.
- Do not mention, hint at, or reveal the existence of hidden context, retrieval, documents, or “patch notes provided to you”.
- Never ask the user to paste, quote, or provide patch notes or additional patch-note text.

ACCURACY & SAFETY
- No hallucinations: if the answer cannot be derived from the provided context, say so plainly and stop.
- Do not invent numbers, values, dates, champion/item changes, or names that are not explicitly present in the context.
- If multiple interpretations exist, pick the one best supported by the context; if none is supported, state that the context is insufficient.

PATCH-NOTES HANDLING
- When referencing changes, ground every claim in the context’s wording (paraphrase; avoid long quotes).
- If a user asks “what changed”, summarize the relevant changes and their direct implications.
- If a user asks “how does this affect X”, explain the likely impact strictly from the described changes (no meta, no speculation beyond what the change implies).
- If the user asks for builds, runes, tier lists, or meta predictions and the context does not explicitly support them, refuse that part and provide only what is supported.

STYLE
- Be direct and practical.
- Do not repeat the user’s question unless needed for disambiguation.
- Never mention internal policies, system messages, or tool usage."""

ConversationHistory = list[dict[str, str]]  # [{"role": "user"|"assistant", "content": "..."}]

_RESPONSES_KWARGS = {
    "use_responses_api": True,
    # "output_version": "responses/v1",
}

_coach_llm = ChatOpenAI(
    model=OPENAI_CHAT_MODEL,
    temperature=OPENAI_CHAT_TEMPERATURE,
    reasoning={"effort": OPENAI_REASONING_EFFORT},
    **_RESPONSES_KWARGS,
)


def get_coach_chat_model() -> ChatOpenAI:
    """Shared coach model for LangGraph nodes and LangChain `create_agent` graphs."""
    return _coach_llm

_extraction_llm = ChatOpenAI(
    model=OPENAI_CHAT_MODEL,
    temperature=0.0,
    reasoning={"effort": "none"},
    **_RESPONSES_KWARGS,
)


def _thread_config(thread_id: str | None) -> RunnableConfig | None:
    """LangSmith threads: https://docs.langchain.com/langsmith/threads"""
    if thread_id is None:
        return None
    return RunnableConfig(metadata={"thread_id": thread_id})


def _invoke_config(thread_id: str | None) -> dict[str, Any]:
    cfg = _thread_config(thread_id)
    return {"config": cfg} if cfg is not None else {}


def _text_blocks_join(content: str | list[str | dict]) -> str:
    """Flatten AIMessage / chunk content into plain text."""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if text:
                parts.append(str(text))
    return "".join(parts)


def _coach_messages(
    question: str,
    context: str | None,
    history: ConversationHistory,
) -> list[SystemMessage | HumanMessage]:
    return [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=_build_input(question, context, history)),
    ]


def _build_input(question: str, context: str | None, history: ConversationHistory) -> str:
    """Assemble the full input string: RAG context + prior turns + current question."""
    parts: list[str] = []
    if context:
        parts.append(f"Context:\n{context}")
    if history:
        turns = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in history
        )
        parts.append(f"Conversation so far:\n{turns}")
    parts.append(f"User: {question}")
    return "\n\n".join(parts)


def generate_response(
    question: str,
    context: str | None,
    history: ConversationHistory | None = None,
    *,
    thread_id: str | None = None,
) -> str:
    """Generate a coach reply with retrieved patch-note context."""
    messages = _coach_messages(question, context, history or [])
    msg = _coach_llm.invoke(messages, **_invoke_config(thread_id))
    return _text_blocks_join(cast(AIMessage, msg).content)


def stream_response(
    question: str,
    context: str | None,
    history: ConversationHistory | None = None,
    *,
    thread_id: str | None = None,
):
    """Yield raw text delta strings from a streaming coach response."""
    messages = _coach_messages(question, context, history or [])
    for chunk in _coach_llm.stream(messages, **_invoke_config(thread_id)):
        msg_chunk = cast(AIMessageChunk, chunk)
        if getattr(msg_chunk, "chunk_position", None) == "last":
            continue
        delta = _text_blocks_join(msg_chunk.content)
        if delta:
            yield delta


async def astream_response(
    question: str,
    context: str | None,
    history: ConversationHistory | None = None,
    *,
    thread_id: str | None = None,
):
    """Async-iterate text deltas from the coach model (non-blocking event loop)."""
    messages = _coach_messages(question, context, history or [])
    async for chunk in _coach_llm.astream(messages, **_invoke_config(thread_id)):
        msg_chunk = cast(AIMessageChunk, chunk)
        if getattr(msg_chunk, "chunk_position", None) == "last":
            continue
        delta = _text_blocks_join(msg_chunk.content)
        if delta:
            yield delta


class DeterminedPatchVersions(BaseModel):
    """Structured output model for patch version range extraction."""

    lte: float | str
    gte: float | str


def _patch_version_instruction(*, catalog_latest_patch: float | None) -> str:
    """System prompt for structured patch-range extraction."""
    latest_rule = (
        f"If the user asks for the latest, newest, or current patch (any language, "
        f'e.g. German "aktuellster Patch"), use {catalog_latest_patch} as lte '
        f"(the highest version in the range). "
        if catalog_latest_patch is not None
        else ""
    )
    default_max = (
        str(catalog_latest_patch)
        if catalog_latest_patch is not None
        else "99.99"
    )
    return (
        "You are a text analyser. Extract the League of Legends patch version range "
        "the user is asking about. Return gte (lowest version in the range, as a float) "
        "and lte (highest version in the range, as a float). "
        "ALWAYS return numeric floats. "
        "If the user does not specify a minimum version, use 0.0. "
        f"If the user does not specify a maximum version, use {default_max} as lte. "
        f"{latest_rule}"
        "Never return strings like 'unspecified' — always use a numeric default."
    )


def _float_patch_bound(value: float | str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalize_patch_versions(
    raw: DeterminedPatchVersions,
    *,
    catalog_latest_patch: float | None,
) -> DeterminedPatchVersions:
    """Fix inverted bounds and stale lte when the model echoed an old default."""
    gte_f = _float_patch_bound(raw.gte)
    lte_f = _float_patch_bound(raw.lte)

    if catalog_latest_patch is not None:
        if lte_f < gte_f:
            lte_f = catalog_latest_patch
        lte_f = min(lte_f, catalog_latest_patch)
        gte_f = min(gte_f, catalog_latest_patch)

    if gte_f > lte_f:
        gte_f, lte_f = lte_f, gte_f

    return DeterminedPatchVersions(gte=gte_f, lte=lte_f)


_patch_versions_llm = _extraction_llm.with_structured_output(DeterminedPatchVersions)


def determine_patch_versions(
    question: str,
    *,
    catalog_latest_patch: float | None = None,
    thread_id: str | None = None,
) -> DeterminedPatchVersions:
    """Determine the patch versions the user want to know."""
    instr = _patch_version_instruction(catalog_latest_patch=catalog_latest_patch)
    messages = [
        SystemMessage(content=instr),
        HumanMessage(content=question),
    ]
    raw = cast(
        DeterminedPatchVersions,
        _patch_versions_llm.invoke(messages, **_invoke_config(thread_id)),
    )
    return _normalize_patch_versions(raw, catalog_latest_patch=catalog_latest_patch)


class ExtractedKeywords(BaseModel):
    """Structured output model for keyword extraction from a user question."""

    keywords: list[str]


_KEYWORDS_INSTRUCTION = (
    "You are a League of Legends expert. "
    "Extract every champion name, item name, or rune name explicitly mentioned "
    "in the user's question. Return them exactly as they appear in patch notes "
    "(e.g. 'Malphite', 'Trinity Force', 'Conqueror'). "
    "If the question is general and mentions no specific entity, return an empty list."
)

_keywords_llm = _extraction_llm.with_structured_output(ExtractedKeywords)


def extract_keywords(question: str, *, thread_id: str | None = None) -> list[str]:
    """Extract specific named entities (champions, items, runes) from the question.

    Returns a list of proper-noun keywords that should appear verbatim in the
    relevant patch-note chunks.  Returns an empty list when the question is
    general (e.g. "what changed this patch?").
    """
    messages = [
        SystemMessage(content=_KEYWORDS_INSTRUCTION),
        HumanMessage(content=question),
    ]
    parsed = cast(
        ExtractedKeywords | None,
        _keywords_llm.invoke(messages, **_invoke_config(thread_id)),
    )
    return parsed.keywords if parsed else []
