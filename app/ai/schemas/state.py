"""LangGraph state for the coach MVP."""

from typing import Literal, NotRequired, Required
from typing_extensions import TypedDict

CoachIntent = Literal[
    "patch_notes",
    "match_analysis",
    "build_evaluation",
    "champion_coaching",
    "item_explanation",
    "training_plan",
    "general_lol_question",
    "fallback",
]


class CoachGraphState(TypedDict):
    """Mutable coach workflow state passed into the outer LangGraph shell."""

    user_message: Required[str]
    conversation_history: Required[list[dict[str, str]]]
    thread_id: NotRequired[str | None]
    top_k: NotRequired[int]

    answer: NotRequired[str]
    errors: NotRequired[list[dict[str, str]]]
