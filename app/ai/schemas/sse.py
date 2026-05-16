"""SSE payload shapes (mirror backend JSON; frontend may duplicate in TypeScript)."""

from typing import Literal, NotRequired

from typing_extensions import TypedDict


class StatusSseData(TypedDict):
    """``event: status`` JSON body."""

    step: str
    label: str
    progress: NotRequired[int | None]


class TokenSseData(TypedDict):
    """``event: token`` JSON body."""

    text: str


class ErrorSseData(TypedDict):
    """``event: error`` JSON body."""

    message: str
    step: NotRequired[str]


class DoneSseData(TypedDict):
    """``event: done`` JSON body."""

    label: NotRequired[str]


class CustomStatusPayload(TypedDict):
    """LangGraph custom-stream status payload."""

    type: Literal["status"]
    step: str
    label: str
    progress: NotRequired[int | None]


class CustomTokenPayload(TypedDict):
    """LangGraph custom-stream token payload."""

    type: Literal["token"]
    text: str
