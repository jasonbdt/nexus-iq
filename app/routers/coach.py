"""Coach chat session CRUD endpoints.

All routes require an authenticated, active user.  Users can only access
their own sessions.
"""
import time
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.routing import APIRouter
from fastapi.responses import StreamingResponse
from langsmith import uuid7
from sqlmodel import select, desc

from ..ai.graphs.coach_mvp import get_coach_compiled_graph
from ..ai.sse import format_sse, sse_from_custom_payload
from ..internal.auth import get_current_active_user
from ..internal.db import SessionDep
from ..internal.logging import get_logger
from ..internal.models import (
    CoachMessage,
    CoachMessageRead,
    CoachSession,
    CoachSessionCreate,
    CoachSessionRead,
    User,
)
from ..internal.services.llm import ConversationHistory

logger = get_logger(__name__)

router = APIRouter(prefix="/coach", tags=["Coach"])

CurrentUser = Annotated[User, Depends(get_current_active_user)]


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_session_or_404(session_id: int, user: User, db: SessionDep) -> CoachSession:
    coach_session = db.get(CoachSession, session_id)
    if coach_session is None or coach_session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return coach_session


# ── Session CRUD ──────────────────────────────────────────────────────────────

@router.get("/sessions", response_model=list[CoachSessionRead])
def list_sessions(user: CurrentUser, db: SessionDep):
    """Return all sessions for the current user (newest first, no messages)."""
    sessions = db.exec(
        select(CoachSession)
        .where(CoachSession.user_id == user.id)
        .order_by(desc(CoachSession.updated_at))
    ).all()
    return [CoachSessionRead(
        id=s.id,
        title=s.title,
        created_at=s.created_at,
        updated_at=s.updated_at,
        messages=[],
    ) for s in sessions]


@router.post("/sessions", response_model=CoachSessionRead, status_code=status.HTTP_201_CREATED)
def create_session(payload: CoachSessionCreate, user: CurrentUser, db: SessionDep):
    """Create a new empty coaching session."""
    coach_session = CoachSession(
        user_id=user.id,
        title=payload.title,
        langsmith_thread_id=str(uuid7()),
    )
    db.add(coach_session)
    db.commit()
    db.refresh(coach_session)
    return CoachSessionRead(
        id=coach_session.id,
        title=coach_session.title,
        created_at=coach_session.created_at,
        updated_at=coach_session.updated_at,
        messages=[],
    )


@router.get("/sessions/{session_id}", response_model=CoachSessionRead)
def get_session(session_id: int, user: CurrentUser, db: SessionDep):
    """Return a single session with all its messages."""
    coach_session = _get_session_or_404(session_id, user, db)
    messages = db.exec(
        select(CoachMessage)
        .where(CoachMessage.session_id == session_id)
        .order_by(CoachMessage.created_at)
    ).all()
    return CoachSessionRead(
        id=coach_session.id,
        title=coach_session.title,
        created_at=coach_session.created_at,
        updated_at=coach_session.updated_at,
        messages=[
            CoachMessageRead(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
                thought_seconds=m.thought_seconds,
            )
            for m in messages
        ],
    )


@router.patch("/sessions/{session_id}", response_model=CoachSessionRead)
def rename_session(session_id: int, payload: CoachSessionCreate, user: CurrentUser, db: SessionDep):
    """Rename a session."""
    coach_session = _get_session_or_404(session_id, user, db)
    coach_session.title = payload.title
    db.add(coach_session)
    db.commit()
    db.refresh(coach_session)
    return CoachSessionRead(
        id=coach_session.id,
        title=coach_session.title,
        created_at=coach_session.created_at,
        updated_at=coach_session.updated_at,
        messages=[],
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: int, user: CurrentUser, db: SessionDep):
    """Delete a session and all its messages."""
    coach_session = _get_session_or_404(session_id, user, db)
    # Delete messages first (no cascade configured)
    messages = db.exec(
        select(CoachMessage).where(CoachMessage.session_id == session_id)
    ).all()
    for msg in messages:
        db.delete(msg)
    db.delete(coach_session)
    db.commit()


# ── Streaming chat ────────────────────────────────────────────────────────────


def _answer_from_updates_payload(data: dict) -> str | None:
    """Return the first node update's ``answer`` if the key is present (including ``\"\"``)."""
    for upd in data.values():
        if isinstance(upd, dict) and "answer" in upd:
            return str(upd["answer"])
    return None


@router.post("/sessions/{session_id}/chat")
async def chat_stream(  # pylint: disable=too-many-statements
    session_id: int, question: str, user: CurrentUser, db: SessionDep
):
    """
    Append the user's question to the session, stream LangGraph pipeline progress
    and answer tokens as Server-Sent Events, then persist the assistant message.

    SSE events:
      event: status — data: {"step","label","progress"?}
      event: reasoning — data: {"text":"..."} (model reasoning summary, meta row only)
      event: token  — data: {"text":"..."}
      event: error  — data: {"message","step"?}
      event: done   — data: {"label"}
    """
    coach_session = _get_session_or_404(session_id, user, db)

    if coach_session.langsmith_thread_id is None:
        coach_session.langsmith_thread_id = str(uuid7())
        db.add(coach_session)

    # Load prior messages for conversation history (before persisting the new one)
    prior_messages = db.exec(
        select(CoachMessage)
        .where(CoachMessage.session_id == session_id)
        .order_by(CoachMessage.created_at)
    ).all()
    history: ConversationHistory = [
        {"role": m.role, "content": m.content} for m in prior_messages
    ]

    # Persist user message immediately
    user_msg = CoachMessage(session_id=session_id, role="user", content=question)
    db.add(user_msg)

    # Update session title from first message
    if len(prior_messages) == 0 and coach_session.title == "New Session":
        coach_session.title = question[:80] + ("…" if len(question) > 80 else "")
        db.add(coach_session)

    db.commit()
    db.refresh(coach_session)
    thread_id = coach_session.langsmith_thread_id

    graph = get_coach_compiled_graph()
    initial_state = {
        "user_message": question,
        "conversation_history": history,
        "thread_id": thread_id,
        "top_k": 15,
    }

    async def event_generator():  # pylint: disable=too-many-branches,too-many-statements
        collected: list[str] = []
        backup_answer = ""
        full_answer: str = ""
        stream_started_at = time.perf_counter()
        first_token_at: float | None = None
        try:
            # LangGraph v2 ``StreamPart`` dicts (type / ns / data).
            async for part in graph.astream(
                initial_state,
                stream_mode=["custom", "updates"],
                version="v2",
            ):
                if not isinstance(part, dict):
                    continue
                st = part.get("type")
                data = part.get("data")
                if st == "custom" and isinstance(data, dict):
                    sse_line = sse_from_custom_payload(data)
                    if sse_line:
                        yield sse_line
                    typ = data.get("type")
                    if typ == "token":
                        piece = str(data.get("text", ""))
                        # collected.append(piece)
                        if piece and first_token_at is None:
                            first_token_at = time.perf_counter()
                elif st == "updates" and isinstance(data, dict):
                    ans = _answer_from_updates_payload(data)
                    if ans is not None:
                        backup_answer = ans
            full_answer = "".join(collected) if collected else backup_answer
            yield format_sse("done", {"label": "Done"})
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.exception("Coach graph stream failed")
            full_answer = "".join(collected) if collected else backup_answer
            yield format_sse("error", {"message": str(exc), "step": "coach_graph"})
            yield format_sse("done", {"label": "Done"})
        finally:
            if first_token_at is not None:
                thought_seconds = max(1, int(round(first_token_at - stream_started_at)))
            else:
                thought_seconds = max(
                    1, int(round(time.perf_counter() - stream_started_at))
                )
            assistant_msg = CoachMessage(
                session_id=session_id,
                role="assistant",
                content=full_answer,
                thought_seconds=thought_seconds,
            )
            db.add(assistant_msg)
            db.commit()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
