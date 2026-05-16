"""Conversation history helpers shared by coach router and LangGraph nodes."""

from app.internal.services.llm import ConversationHistory


def resolved_question(question: str, history: ConversationHistory) -> str:
    """Prepend recent turns so LLM helpers can resolve pronouns."""
    if not history:
        return question
    recent = history[-6:]
    turns = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in recent
    )
    return f"{turns}\nUser: {question}"
