"""Tests for heuristic coach intent labels (used in tests / optional helpers)."""

from app.ai.nodes.intent import classify_intent


def test_classify_intent_patch_notes_default():
    """Default questions map to patch-notes workflow."""
    assert classify_intent("What changed for Vayne in patch 26.8?") == "patch_notes"


def test_classify_intent_match_analysis():
    """Match-loss phrasing maps to match analysis label."""
    assert classify_intent("Why did I lose my last game?") == "match_analysis"


def test_classify_intent_training_plan():
    """Training/drill phrasing maps to training plan label."""
    assert classify_intent("Give me a 15-minute drill for kiting") == "training_plan"
