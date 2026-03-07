"""Coach chat session CRUD endpoints.

All routes require an authenticated, active user.  Users can only access
their own sessions.
"""
import json
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.routing import APIRouter
from fastapi.responses import StreamingResponse
from sqlmodel import select, desc

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
from ..internal.services.llm import (
    ConversationHistory,
    stream_response,
    determine_patch_versions,
    extract_keywords,
)
from ..internal.services.rag import build_rag_context

logger = get_logger(__name__)

router = APIRouter(prefix="/coach", tags=["Coach"])

CurrentUser = Annotated[User, Depends(get_current_active_user)]


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_session_or_404(session_id: int, user: User, db: SessionDep) -> CoachSession:
    coach_session = db.get(CoachSession, session_id)
    if coach_session is None or coach_session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return coach_session


def _resolved_question(question: str, history: ConversationHistory) -> str:
    """Prepend the last few conversation turns so LLM helpers can resolve pronouns."""
    if not history:
        return question
    recent = history[-6:]  # last 3 user+assistant pairs at most
    turns = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in recent
    )
    return f"{turns}\nUser: {question}"


async def _build_context(
    question: str,
    history: ConversationHistory | None = None,
    top_k: int = 15,
) -> str:
    resolved = _resolved_question(question, history or [])
    patch_versions = determine_patch_versions(resolved)
    keywords = extract_keywords(resolved)
    return await build_rag_context(question, patch_versions, keywords, top_k=top_k)


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
    coach_session = CoachSession(user_id=user.id, title=payload.title)
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
        messages=[CoachMessageRead(
            id=m.id, role=m.role, content=m.content, created_at=m.created_at
        ) for m in messages],
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

@router.post("/sessions/{session_id}/chat")
async def chat_stream(session_id: int, question: str, user: CurrentUser, db: SessionDep):
    """
    Append the user's question to the session, stream the AI response as
    Server-Sent Events, then persist the completed assistant message.

    SSE format:
      data: {"delta": "<token>"}   — one per token
      data: [DONE]                 — end of stream
    """
    coach_session = _get_session_or_404(session_id, user, db)

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

    # Build RAG context, resolving pronouns/references via conversation history
    context = await _build_context(question, history=history)

    # Collect the full response while streaming so we can persist it
    collected: list[str] = []

    def event_generator():
        for delta in stream_response(question, context, history=history):
            collected.append(delta)
            yield f"data: {json.dumps({'delta': delta})}\n\n"

        # Persist assistant message after stream completes
        full_answer = "".join(collected)
        assistant_msg = CoachMessage(
            session_id=session_id, role="assistant", content=full_answer
        )
        db.add(assistant_msg)
        db.commit()

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
