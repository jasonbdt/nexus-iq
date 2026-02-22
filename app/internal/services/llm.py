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


def generate_response(question: str, context: str | None) -> str:
    """Generate a response using GPT-5.2-mini with retrieved context."""
    response = client.responses.create(
        model="gpt-5-mini",
        instructions=SYSTEM_PROMPT,
        input=f"Context:\n{context}\n\nQuestion: {question}"
    )

    return response.output_text


class DeterminedPatchVersions(BaseModel):
    lte: float | str
    gte: float | str

def determine_patch_versions(question: str):
    """Determine the patch versions the user want to know"""
    response = client.responses.parse(
        model="gpt-5-mini",
        instructions=f"""You are an text analyzer with the task to figure out
        the specific range of league of legends patch versions, that the user
        asked for. The user may ask what updates Vayne has undergone since
        Patch 25.20. The lowest version is then 25.20. If the user does not
        specify a maximum version, use 26.3.""",
        input=question,
        text_format=DeterminedPatchVersions,
    )

    return response.output_parsed