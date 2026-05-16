"""Tests for structured assistant text extraction (no string flattening)."""

from langchain_core.messages import AIMessageChunk

from app.ai.utils.streaming_text import (
    answer_text_blocks_delta,
    assistant_text_blocks_delta,
    reasoning_summary_delta,
)


def test_answer_text_blocks_delta_ignores_plain_string_when_tool_call_chunks():
    """String ``content`` paired with ``tool_call_chunks`` is treated as tool-arg streaming."""
    chunk = AIMessageChunk(
        content='{"lte":26.9,"gte":25.22}',
        tool_call_chunks=[
            {"name": "retrieve_patch_notes", "args": '{"lte"', "id": "call_1", "index": 0}
        ],
    )
    assert answer_text_blocks_delta(chunk) == ""


def test_answer_text_blocks_delta_returns_plain_string_without_tool_chunks():
    """Responses-style plain-string deltas must be preserved."""
    chunk = AIMessageChunk(content="Hello")
    assert answer_text_blocks_delta(chunk) == "Hello"


def test_answer_text_blocks_delta_concatenates_text_blocks():
    chunk = AIMessageChunk(content=[{"type": "text", "text": "Hello"}])
    assert answer_text_blocks_delta(chunk) == "Hello"


def test_answer_text_blocks_delta_handles_openai_output_text_blocks():
    chunk = AIMessageChunk(content=[{"type": "output_text", "text": "Visible answer"}])
    assert answer_text_blocks_delta(chunk) == "Visible answer"


def test_reasoning_summary_delta_extracts_reasoning_only():
    chunk = AIMessageChunk(
        content=[
            {
                "type": "reasoning",
                "summary": [{"type": "summary_text", "text": "Brief rationale."}],
            }
        ]
    )
    assert reasoning_summary_delta(chunk) == "Brief rationale."
    assert answer_text_blocks_delta(chunk) == ""


def test_answer_text_blocks_delta_skips_non_text_blocks():
    chunk = AIMessageChunk(
        content=[
            {"type": "text", "text": "Visible"},
            {"type": "other", "foo": "bar"},
        ]
    )
    assert answer_text_blocks_delta(chunk) == "Visible"


def test_assistant_text_blocks_delta_combines_reasoning_and_answer():
    chunk = AIMessageChunk(
        content=[
            {
                "type": "reasoning",
                "summary": [{"type": "summary_text", "text": "Thinking."}],
            },
            {"type": "text", "text": "Hi"},
        ]
    )
    assert assistant_text_blocks_delta(chunk) == "Thinking.Hi"


def test_answer_text_blocks_delta_suppresses_concatenated_json_objects():
    """Tool args sometimes stream as glued JSON dicts without ``tool_call_chunks`` yet."""
    chunk = AIMessageChunk(
        content='{"lte":26.9,"gte":25.22}{"keywords":["Malphite"]}',
    )
    assert answer_text_blocks_delta(chunk) == ""


def test_answer_text_blocks_delta_suppresses_json_when_tool_calls_present():
    chunk = AIMessageChunk(
        content='{"partial":true}',
        tool_call_chunks=[],
        tool_calls=[
            {
                "name": "retrieve_patch_notes",
                "args": {},
                "id": "call_1",
                "type": "tool_call",
            }
        ],
    )
    assert answer_text_blocks_delta(chunk) == ""
