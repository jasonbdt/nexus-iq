"""Extract streamable assistant text from LangChain message chunks (no string flattening)."""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage, AIMessageChunk


def _string_is_concatenated_json_objects(s: str) -> bool:
    """True if *s* is only whitespace and one or more JSON objects (``{...}{...}``)."""
    t = s.strip()
    if not t.startswith("{"):
        return False
    dec = json.JSONDecoder()
    pos = 0
    try:
        while pos < len(t):
            while pos < len(t) and t[pos] in " \n\r\t":
                pos += 1
            if pos >= len(t):
                break
            _, end = dec.raw_decode(t, pos)
            pos = end
        return pos >= len(t)
    except json.JSONDecodeError:
        return False


def reasoning_summary_delta(chunk: AIMessage | AIMessageChunk) -> str:
    """User-visible reasoning summary lines from ``type: reasoning`` blocks only."""
    content = chunk.content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "reasoning":
            continue
        for item in block.get("summary") or ():
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
    return "".join(parts)


def _suppress_string_tool_args(chunk: AIMessageChunk, s: str) -> bool:
    """True when string ``content`` should not be shown as assistant prose."""
    if chunk.tool_call_chunks:
        return True
    tc = getattr(chunk, "tool_calls", None) or ()
    if tc and s.strip().startswith("{"):
        return True
    return _string_is_concatenated_json_objects(s)


def answer_text_blocks_delta(chunk: AIMessage | AIMessageChunk) -> str:
    """Streamable assistant answer text only (no reasoning, no tool-arg JSON).

    - **List** ``content``: only ``type`` ``text`` and ``output_text`` blocks.
    - **String** ``content``: plain prose when not tool-call argument streaming.
    """
    content = chunk.content
    if isinstance(content, str):
        if isinstance(chunk, AIMessageChunk) and _suppress_string_tool_args(chunk, content):
            return ""
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text" and block.get("text"):
            parts.append(str(block["text"]))
            continue
        if btype == "output_text" and block.get("text"):
            parts.append(str(block["text"]))
    return "".join(parts)


def assistant_text_blocks_delta(chunk: AIMessage | AIMessageChunk) -> str:
    """Full visible delta: reasoning summary plus answer (legacy / tool-return assembly)."""
    return reasoning_summary_delta(chunk) + answer_text_blocks_delta(chunk)
