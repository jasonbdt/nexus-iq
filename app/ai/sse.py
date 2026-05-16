"""Format Server-Sent Events for coach streaming."""

import json
from typing import Any


def format_sse(event: str, data: dict[str, Any]) -> str:
    """One SSE message: event line + JSON data line + blank line."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def sse_from_custom_payload(custom: dict[str, Any]) -> str | None:
    """Map LangGraph custom writer dict to an SSE string, or None if unknown."""
    typ = custom.get("type")
    if typ == "status":
        body: dict[str, Any] = {
            "step": custom["step"],
            "label": custom["label"],
        }
        if custom.get("progress") is not None:
            body["progress"] = custom["progress"]
        return format_sse("status", body)
    if typ == "token":
        return format_sse("token", {"text": custom.get("text", "")})
    if typ == "reasoning":
        return format_sse("reasoning", {"text": custom.get("text", "")})
    if typ == "error":
        body = {"message": custom["message"]}
        if custom.get("step") is not None:
            body["step"] = custom["step"]
        return format_sse("error", body)
    return None
