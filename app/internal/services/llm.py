import os

from openai import OpenAI
from pydantic import BaseModel

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """You are “NexusIQ AI Coach”, a League of Legends patch-notes analyst and Q&A assistant.

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
) -> str:
    """Generate a response using GPT-5-mini with retrieved context."""
    response = client.responses.create(
        model="gpt-5-mini",
        instructions=SYSTEM_PROMPT,
        input=_build_input(question, context, history or []),
    )
    return response.output_text


def stream_response(
    question: str,
    context: str | None,
    history: ConversationHistory | None = None,
):
    """Yield raw text delta strings from a streaming GPT-5-mini response."""
    with client.responses.stream(
        model="gpt-5-mini",
        instructions=SYSTEM_PROMPT,
        input=_build_input(question, context, history or []),
    ) as stream:
        for event in stream:
            # The Responses API emits response.output_text.delta events
            if event.type == "response.output_text.delta":
                yield event.delta


class DeterminedPatchVersions(BaseModel):
    lte: float | str
    gte: float | str


def determine_patch_versions(question: str) -> DeterminedPatchVersions:
    """Determine the patch versions the user want to know."""
    response = client.responses.parse(
        model="gpt-5-mini",
        instructions=(
            "You are a text analyser. Extract the League of Legends patch version range "
            "the user is asking about. Return gte (lowest version, as a float) and lte (highest version, as a float). "
            "ALWAYS return numeric floats. "
            "If the user does not specify a minimum version, use 0.0. "
            "If the user does not specify a maximum version, use 26.4. "
            "Never return strings like 'unspecified' — always use a numeric default."
        ),
        input=question,
        text_format=DeterminedPatchVersions,
    )
    return response.output_parsed


class ExtractedKeywords(BaseModel):
    keywords: list[str]


def extract_keywords(question: str) -> list[str]:
    """Extract specific named entities (champions, items, runes) from the question.

    Returns a list of proper-noun keywords that should appear verbatim in the
    relevant patch-note chunks.  Returns an empty list when the question is
    general (e.g. "what changed this patch?").
    """
    response = client.responses.parse(
        model="gpt-5-mini",
        instructions=(
            "You are a League of Legends expert. "
            "Extract every champion name, item name, or rune name explicitly mentioned "
            "in the user's question. Return them exactly as they appear in patch notes "
            "(e.g. 'Malphite', 'Trinity Force', 'Conqueror'). "
            "If the question is general and mentions no specific entity, return an empty list."
        ),
        input=question,
        text_format=ExtractedKeywords,
    )
    return response.output_parsed.keywords if response.output_parsed else []
