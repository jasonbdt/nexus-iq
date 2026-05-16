"""Heuristic intent labels (kept for tests and optional tooling; routing is LLM-driven)."""

from __future__ import annotations

import re

from app.ai.schemas.state import CoachIntent

# Keywords → stub workflows (no live match/training pipeline yet)
_MATCH_PATTERNS = (
    r"\bwhy did i lose\b",
    r"\blast game\b",
    r"\blast match\b",
    r"\bmatch history\b",
    r"\bmy last (ranked )?game\b",
)
_TRAINING_PATTERNS = (
    r"\bdrill\b",
    r"\btraining plan\b",
    r"\bpractice routine\b",
)


def classify_intent(text: str) -> CoachIntent:
    """Rule-based intent for tests and future hybrid routing."""
    t = text.lower()
    if any(re.search(p, t) for p in _MATCH_PATTERNS):
        return "match_analysis"
    if any(re.search(p, t) for p in _TRAINING_PATTERNS):
        return "training_plan"
    return "patch_notes"
