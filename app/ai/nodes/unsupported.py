"""Stub specialist for coach workflows that are not implemented yet."""

from langchain.agents import create_agent

from app.internal.services.llm import get_coach_chat_model

_STUB_SPECIALIST_PROMPT = (
    "You are a League of Legends coach assistant. "
    "The user asked for match review, loss analysis, training plans, drills, or similar. "
    "Those workflows are not available in NexusIQ yet. "
    "Reply in 2–4 short sentences: say it is not available, and suggest they ask about "
    "patch notes, balance changes, or champion/item updates instead. "
    "Do not invent features or tools."
)


def build_stub_specialist_agent():
    """Minimal specialist agent (no tools) for placeholder workflows."""
    return create_agent(
        get_coach_chat_model(),
        tools=[],
        system_prompt=_STUB_SPECIALIST_PROMPT,
        name="placeholder_workflows_specialist",
    )
