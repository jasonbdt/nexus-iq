"""Conversation ownership, history and split stream persistence boundaries."""
from collections.abc import Iterator
from dataclasses import dataclass, asdict

from app.domain.errors import NotFound
from app.domain.models import CoachSession, CoachMessage, utc_now
from app.domain.policies import initial_title
from .ports import UnitOfWorkFactory
from .rag import Retrieval


@dataclass
class Coaching:
    """No database session remains alive while tokens are streamed."""

    uow: UnitOfWorkFactory
    retrieval: Retrieval

    @staticmethod
    def _owned(work, identity: int, user_id: int) -> CoachSession:
        conversation = work.coaching.get(identity)
        if conversation is None or conversation.user_id != user_id:
            raise NotFound('Session not found')
        return conversation

    def list(self, user_id: int) -> list[dict]:
        """List metadata only, with the existing empty messages arrays."""
        with self.uow() as work:
            return [{**asdict(item), 'messages': []} for item in work.coaching.list(user_id)]

    def create(self, user_id: int, title: str) -> CoachSession:
        """Create an empty user-owned conversation."""
        with self.uow() as work:
            conversation = work.coaching.save(CoachSession(user_id=user_id, title=title))
            work.commit()
            return conversation

    def get(self, identity: int, user_id: int) -> CoachSession:
        """Read a conversation and its ordered messages."""
        with self.uow() as work:
            return self._owned(work, identity, user_id)

    def rename(self, identity: int, user_id: int, title: str) -> dict:
        """Rename while preserving the metadata-only PATCH response."""
        with self.uow() as work:
            conversation = self._owned(work, identity, user_id)
            conversation.title = title
            conversation.updated_at = utc_now()
            result = work.coaching.save(conversation)
            work.commit()
            return {**asdict(result), 'messages': []}

    def delete(self, identity: int, user_id: int) -> None:
        """Delete the owned conversation and all messages together."""
        with self.uow() as work:
            work.coaching.delete(self._owned(work, identity, user_id))
            work.commit()

    async def chat(self, identity: int, user_id: int, question: str) -> Iterator[str]:
        """Save the question, build context, then return a completion-aware iterator."""
        with self.uow() as work:
            conversation = self._owned(work, identity, user_id)
            history = [{'role': item.role, 'content': item.content}
                       for item in conversation.messages]
            if not history and conversation.title == 'New Session':
                conversation.title = initial_title(question)
            conversation.messages.append(CoachMessage(
                session_id=identity, role='user', content=question,
            ))
            work.coaching.save(conversation)
            work.commit()
        context = await self.retrieval.context(question, history=history)

        def generate():
            collected = []
            # Closing this generator on disconnect also closes the SDK stream.
            stream = self.retrieval.ai.stream(question, context, history)
            try:
                for delta in stream:
                    collected.append(delta)
                    yield delta
            finally:
                close = getattr(stream, 'close', None)
                if close:
                    close()
            with self.uow() as work:
                completed = self._owned(work, identity, user_id)
                completed.messages.append(CoachMessage(
                    session_id=identity, role='assistant', content=''.join(collected),
                ))
                work.coaching.save(completed)
                work.commit()
        return generate()
