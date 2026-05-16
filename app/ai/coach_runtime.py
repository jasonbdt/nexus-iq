"""Request-scoped context for coach tools (thread id, history, SSE writer)."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from langgraph.types import StreamWriter


@dataclass
class CoachRequestRuntime:
    """Per-chat-turn data visible to LangChain tools and retrieval helpers."""

    user_message: str
    conversation_history: list[dict[str, str]]
    thread_id: str | None
    top_k: int
    writer: StreamWriter | None
    #: True once ``STEP_GENERATE_ANSWER`` was emitted (patch RAG, stub, or first user token).
    generate_answer_status_emitted: bool = False


coach_request_ctx: ContextVar[CoachRequestRuntime | None] = ContextVar(
    "coach_request_ctx",
    default=None,
)
