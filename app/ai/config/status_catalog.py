"""Pipeline step ids and user-visible labels (single source of truth)."""

from collections.abc import Callable

STEP_ANALYZE_REQUEST = "analyze_request"
STEP_DETERMINE_PATCH_RANGE = "determine_patch_range"
STEP_RESOLVE_CATALOG_PATCH = "resolve_catalog_patch"
STEP_RETRIEVE_PATCH_NOTES = "retrieve_patch_notes"
STEP_GENERATE_ANSWER = "generate_answer"
STEP_WORKFLOW_UNAVAILABLE = "workflow_unavailable"

STEP_LABELS: dict[str, str] = {
    STEP_ANALYZE_REQUEST: "Analyzing request",
    STEP_DETERMINE_PATCH_RANGE: "Determining patch version range",
    STEP_RESOLVE_CATALOG_PATCH: "Resolving current patch from catalog",
    STEP_RETRIEVE_PATCH_NOTES: "Searching relevant patch notes",
    STEP_WORKFLOW_UNAVAILABLE: "Stopping workflow (not available yet)",
    STEP_GENERATE_ANSWER: "Generating coaching answer",
}

StreamWriterFn = Callable[[dict], None]


def emit_status(
    writer: StreamWriterFn,
    step_id: str,
    *,
    progress: int | None = None,
) -> None:
    """Emit a real pipeline status event (custom stream)."""
    label = STEP_LABELS.get(step_id, step_id.replace("_", " ").title())
    payload: dict = {"type": "status", "step": step_id, "label": label}
    if progress is not None:
        payload["progress"] = progress
    writer(payload)
