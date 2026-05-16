"""LangGraph coach shell: Supervisor first, then RAG agent on demand.

The **supervisor** is a LangChain ``create_agent`` that delegates patch Q&A to a
**RAG agent** (second ``create_agent``). The RAG agent exposes a single tool,
``retrieve_patch_notes``, which wraps :func:`retrieve_patch_notes_context`.
"""

from __future__ import annotations

from functools import lru_cache

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.types import StreamWriter

from app.ai.coach_runtime import CoachRequestRuntime, coach_request_ctx
from app.ai.config.status_catalog import (
    STEP_ANALYZE_REQUEST,
    STEP_GENERATE_ANSWER,
    STEP_WORKFLOW_UNAVAILABLE,
    emit_status,
)
from app.ai.nodes.patch_notes import retrieve_patch_notes_context
from app.ai.nodes.unsupported import build_stub_specialist_agent
from app.ai.schemas.state import CoachGraphState
from app.ai.utils.streaming_text import (
    answer_text_blocks_delta,
    reasoning_summary_delta,
)
from app.internal.services.llm import get_coach_chat_model

_RAG_AGENT_PROMPT = (
    "You are the NexusIQ **RAG (patch-notes) agent**, invoked after the main coach "
    "supervisor.\n"
    "Do not emit any user-visible text until **retrieve_patch_notes** has returned "
    "(no preamble, hedging, or claims about missing context before the tool runs).\n"
    "Always call **retrieve_patch_notes** first with a short natural-language query "
    "that captures what to look up (champions, items, systems, patch scope).\n"
    "Then answer using only the text returned by that tool. "
    "If the tool returns empty context, say you cannot find it in the patch notes. "
    "Never invent changes not supported by the tool output."
)

_CONSULT_TOOL_NAMES = frozenset(
    {
        "consult_rag_agent",
        "consult_placeholder_workflows_specialist",
    }
)

_SUPERVISOR_PROMPT = (
    "You are NexusIQ AI Coach (**supervisor**), orchestrating downstream agents.\n"
    "- Use **consult_rag_agent** first for patch notes, balance changes, champion or "
    "item changes, or anything answerable from official patch text. That agent calls "
    "**retrieve_patch_notes** internally.\n"
    "- Use **consult_placeholder_workflows_specialist** for match reviews, why the "
    "user lost a game, match history analysis, training plans, drills, or practice routines.\n"
    "When a tool returns a complete user-facing reply, pass it through with at most "
    "light edits for tone. Do not mention tools, agents, or internal steps."
)


@lru_cache(maxsize=1)
def _rag_agent():
    @tool
    async def retrieve_patch_notes(query: str) -> str:
        """Retrieve embedded League of Legends patch-note passages for the query.

        Pass a concise natural-language search string (champions, items, mechanics).
        """
        return await retrieve_patch_notes_context(vector_query=query)

    return create_agent(
        get_coach_chat_model(),
        tools=[retrieve_patch_notes],
        system_prompt=_RAG_AGENT_PROMPT,
        name="rag_patch_notes_agent",
    )


@lru_cache(maxsize=1)
def _stub_specialist_agent():
    return build_stub_specialist_agent()


def _subagent_runnable_config() -> RunnableConfig | None:
    rt = coach_request_ctx.get()
    if rt is None or rt.thread_id is None:
        return None
    return RunnableConfig(metadata={"thread_id": rt.thread_id})


def _checkpoint_ns_is_nested(metadata: object) -> bool:
    """True when stream event comes from a nested graph (e.g. RAG agent inside a tool)."""
    if not isinstance(metadata, dict):
        return False
    ns = metadata.get("langgraph_checkpoint_ns")
    return isinstance(ns, str) and "|" in ns


async def _stream_agent_run_to_text(
    agent,
    payload: dict,
    cfg: RunnableConfig | None,
) -> str:
    """Run a compiled agent for tool return text (no SSE tokens)."""
    parts: list[str] = []
    kwargs: dict = {"version": "v2"}
    if cfg is not None:
        kwargs["config"] = cfg
    async for ev in agent.astream_events(payload, **kwargs):
        if ev.get("event") != "on_chat_model_stream":
            continue
        chunk = ev.get("data", {}).get("chunk")
        if not isinstance(chunk, (AIMessage, AIMessageChunk)):
            continue
        delta = answer_text_blocks_delta(chunk)
        if not delta:
            continue
        parts.append(delta)
    return "".join(parts)


@tool
async def consult_rag_agent(request: str) -> str:
    """Delegate to the RAG patch-notes agent (uses ``retrieve_patch_notes``).

    Use for champion/item/rune changes, patch summaries, and meta questions that
    should be answered strictly from official patch text.
    """
    agent = _rag_agent()
    cfg = _subagent_runnable_config()
    payload = {"messages": [HumanMessage(content=request)]}
    return await _stream_agent_run_to_text(agent, payload, cfg)


@tool
async def consult_placeholder_workflows_specialist(request: str) -> str:
    """Unsupported flows: last-game analysis, match review, training plans, drills.

    Use when the user wants coaching that requires match history or structured training
    pipelines that are not implemented yet.
    """
    rt = coach_request_ctx.get()
    if rt and rt.writer:
        emit_status(rt.writer, STEP_WORKFLOW_UNAVAILABLE)
        emit_status(rt.writer, STEP_GENERATE_ANSWER)
        rt.generate_answer_status_emitted = True
    agent = _stub_specialist_agent()
    cfg = _subagent_runnable_config()
    payload = {"messages": [HumanMessage(content=request)]}
    return await _stream_agent_run_to_text(agent, payload, cfg)


@lru_cache(maxsize=1)
def get_supervisor_agent():
    """Compiled LangChain supervisor (cached)."""
    return create_agent(
        get_coach_chat_model(),
        tools=[
            consult_rag_agent,
            # consult_placeholder_workflows_specialist,
        ],
        system_prompt=_SUPERVISOR_PROMPT,
        name="coach_supervisor",
    )


def _history_to_messages(
    history: list[dict[str, str]],
    current_user: str,
) -> list[HumanMessage | AIMessage]:
    """Map stored coach history plus the latest user turn to LangChain messages."""
    out: list[HumanMessage | AIMessage] = []
    for turn in history:
        if turn.get("role") == "user":
            out.append(HumanMessage(content=turn["content"]))
        elif turn.get("role") == "assistant":
            out.append(AIMessage(content=turn["content"]))
    out.append(HumanMessage(content=current_user))
    return out


async def supervisor_node(  # pylint: disable=too-many-branches
    state: CoachGraphState, writer: StreamWriter
) -> dict:
    """Run the LangChain supervisor agent and map model/tool events to SSE custom payloads."""
    rt = CoachRequestRuntime(
        user_message=state["user_message"],
        conversation_history=state["conversation_history"],
        thread_id=state.get("thread_id"),
        top_k=int(state.get("top_k", 15)),
        writer=writer,
    )
    token = coach_request_ctx.set(rt)
    parts: list[str] = []
    try:
        emit_status(writer, STEP_ANALYZE_REQUEST)
        agent = get_supervisor_agent()
        messages = _history_to_messages(rt.conversation_history, rt.user_message)
        cfg: RunnableConfig | None = (
            RunnableConfig(metadata={"thread_id": rt.thread_id}) if rt.thread_id else None
        )
        emit_user_tokens = True
        async for ev in agent.astream_events(
            {"messages": messages},
            config=cfg,
            version="v2",
        ):
            et = ev.get("event")
            if et == "on_chat_model_stream":
                nested = _checkpoint_ns_is_nested(ev.get("metadata"))
                # Outer model while a consult tool runs: suppress (tool args / planning).
                # Nested streams are the subagent (e.g. RAG) — they must not be skipped or
                # the user sees zero tokens (all real prose streams as nested today).
                if not emit_user_tokens and not nested:
                    continue
                chunk = ev.get("data", {}).get("chunk")
                if isinstance(chunk, (AIMessage, AIMessageChunk)):
                    r_delta = reasoning_summary_delta(chunk)
                    if r_delta:
                        writer({"type": "reasoning", "text": r_delta})
                    a_delta = answer_text_blocks_delta(chunk)
                    if a_delta:
                        if not rt.generate_answer_status_emitted:
                            emit_status(writer, STEP_GENERATE_ANSWER)
                            rt.generate_answer_status_emitted = True
                        writer({"type": "token", "text": a_delta})
                        parts.append(a_delta)
            elif et == "on_tool_start":
                name = ev.get("name") or "tool"
                if name in _CONSULT_TOOL_NAMES:
                    emit_user_tokens = False
                writer(
                    {
                        "type": "status",
                        "step": "supervisor_tool",
                        "label": f"Calling {name.replace('_', ' ')}... TEST",
                    }
                )
            elif et == "on_tool_end":
                name = ev.get("name") or ""
                if name in _CONSULT_TOOL_NAMES:
                    emit_user_tokens = True
            elif et == "on_tool_error":
                name = ev.get("name") or ""
                if name in _CONSULT_TOOL_NAMES:
                    emit_user_tokens = True
        ans = "".join(parts)
        return {"answer": ans}
    finally:
        coach_request_ctx.reset(token)
