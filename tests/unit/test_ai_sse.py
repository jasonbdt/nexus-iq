"""SSE formatting helpers for coach streaming."""

import json

from app.ai.sse import format_sse, sse_from_custom_payload
from app.routers.coach import _answer_from_updates_payload


def test_format_sse_structure():
    """SSE frames contain event name and JSON data line."""
    raw = format_sse("status", {"step": "x", "label": "Y"})
    assert raw.startswith("event: status\n")
    assert "data: " in raw
    assert raw.endswith("\n\n")
    payload = json.loads(raw.split("data: ", 1)[1].split("\n", 1)[0])
    assert payload == {"step": "x", "label": "Y"}


def test_sse_from_custom_status_and_token():
    """Custom writer dicts map to status and token SSE events."""
    s = sse_from_custom_payload({"type": "status", "step": "a", "label": "B", "progress": 3})
    assert s is not None
    assert "event: status" in s
    t = sse_from_custom_payload({"type": "token", "text": "hi"})
    assert t is not None
    assert "event: token" in t


def test_sse_from_custom_reasoning():
    """Reasoning deltas map to ``event: reasoning``."""
    r = sse_from_custom_payload({"type": "reasoning", "text": "Planning retrieval."})
    assert r is not None
    assert "event: reasoning" in r
    assert "Planning retrieval." in r


def test_answer_from_updates_payload_empty_string():
    """``answer: \"\"`` must be returned, not skipped as falsy."""
    assert _answer_from_updates_payload({"supervisor": {"answer": ""}}) == ""


def test_answer_from_updates_payload_missing_key():
    """Updates without ``answer`` do not match."""
    assert _answer_from_updates_payload({"supervisor": {"foo": "bar"}}) is None
