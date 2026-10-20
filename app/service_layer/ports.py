"""Typed boundaries implemented by infrastructure adapters and test fakes."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Protocol, Self

from app.domain.models import User, Summoner, Match, CoachSession


class Users(Protocol):
    """User aggregate storage, including roles and linked accounts."""

    @abstractmethod
    def get(self, identity: int) -> User | None:
        """Get through this port."""
        raise NotImplementedError

    @abstractmethod
    def by_email(self, email: str) -> User | None:
        """By email through this port."""
        raise NotImplementedError

    @abstractmethod
    def list(self, offset: int, limit: int) -> list[User]:
        """List through this port."""
        raise NotImplementedError

    @abstractmethod
    def save(self, user: User) -> User:
        """Save through this port."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, user: User) -> None:
        """Delete through this port."""
        raise NotImplementedError


class Summoners(Protocol):
    """Cached player profiles and their ranked queues."""

    @abstractmethod
    def get(self, puuid: str) -> Summoner | None:
        """Get through this port."""
        raise NotImplementedError

    @abstractmethod
    def by_name(self, game_name: str, tag_line: str) -> Summoner | None:
        """By name through this port."""
        raise NotImplementedError

    @abstractmethod
    def save(self, summoner: Summoner) -> Summoner:
        """Save through this port."""
        raise NotImplementedError


class Matches(Protocol):
    """Complete match graphs."""

    @abstractmethod
    def get(self, match_id: str) -> Match | None:
        """Get through this port."""
        raise NotImplementedError

    @abstractmethod
    def recent(self, puuid: str, count: int) -> list[Match]:
        """Recent through this port."""
        raise NotImplementedError

    @abstractmethod
    def save(self, match: Match) -> Match:
        """Save through this port."""
        raise NotImplementedError


class Coaching(Protocol):
    """Conversations with their ordered messages."""

    @abstractmethod
    def get(self, identity: int) -> CoachSession | None:
        """Get through this port."""
        raise NotImplementedError

    @abstractmethod
    def list(self, user_id: int) -> list[CoachSession]:
        """List through this port."""
        raise NotImplementedError

    @abstractmethod
    def save(self, session: CoachSession) -> CoachSession:
        """Save through this port."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, session: CoachSession) -> None:
        """Delete through this port."""
        raise NotImplementedError


class UnitOfWork(Protocol):
    """Explicit atomic writes and rollback by default."""

    users: Users
    summoners: Summoners
    matches: Matches
    coaching: Coaching

    @abstractmethod
    def __enter__(self) -> Self:
        """  enter   through this port."""
        raise NotImplementedError

    @abstractmethod
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """  exit   through this port."""
        raise NotImplementedError

    @abstractmethod
    def commit(self) -> None:
        """Commit through this port."""
        raise NotImplementedError

    @abstractmethod
    def rollback(self) -> None:
        """Rollback through this port."""
        raise NotImplementedError


UnitOfWorkFactory = Callable[[], UnitOfWork]


class Riot(Protocol):
    """External data converted to application entities at the boundary."""

    @abstractmethod
    async def profile(self, game_name: str, tag_line: str) -> Summoner | None:
        """Profile through this port."""
        raise NotImplementedError

    @abstractmethod
    async def profile_by_puuid(self, puuid: str) -> Summoner | None:
        """Profile by puuid through this port."""
        raise NotImplementedError

    @abstractmethod
    async def match(self, match_id: str, region: str) -> Match | None:
        """Match through this port."""
        raise NotImplementedError

    @abstractmethod
    async def match_ids(self, puuid: str, region: str, count: int) -> list[str]:
        """Match ids through this port."""
        raise NotImplementedError


class Security(Protocol):
    """Password and token operations without web dependencies."""

    @abstractmethod
    def hash_password(self, password: str) -> str:
        """Hash password through this port."""
        raise NotImplementedError

    @abstractmethod
    def verify_password(self, plain: str, hashed: str) -> bool:
        """Verify password through this port."""
        raise NotImplementedError

    @abstractmethod
    def token(self, email: str, role: str) -> str:
        """Token through this port."""
        raise NotImplementedError

    @abstractmethod
    def subject(self, token: str) -> str | None:
        """Subject through this port."""
        raise NotImplementedError


class Updates(Protocol):
    """Queue, progress queries and already-decoded progress notifications."""

    @abstractmethod
    def enqueue(self, puuid: str, count: int) -> None:
        """Enqueue through this port."""
        raise NotImplementedError

    @abstractmethod
    async def progress(self, puuid: str) -> tuple[int, int]:
        """Progress through this port."""
        raise NotImplementedError

    @abstractmethod
    def subscribe(self, puuid: str) -> AsyncIterator[dict | str | bytes | None]:
        """Subscribe through this port."""
        raise NotImplementedError


class AI(Protocol):
    """Language generation and embeddings."""

    @abstractmethod
    def versions(self, question: str) -> tuple[float | str, float | str]:
        """Versions through this port."""
        raise NotImplementedError

    @abstractmethod
    def keywords(self, question: str) -> list[str]:
        """Keywords through this port."""
        raise NotImplementedError

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Embed through this port."""
        raise NotImplementedError

    @abstractmethod
    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Embed many through this port."""
        raise NotImplementedError

    @abstractmethod
    def answer(self, question: str, context: str) -> str:
        """Answer through this port."""
        raise NotImplementedError

    @abstractmethod
    def stream(self, question: str, context: str,
               history: list[dict[str, str]]) -> Iterator[str]:
        """Stream through this port."""
        raise NotImplementedError


class Vectors(Protocol):
    """Patch-note retrieval and indexing."""

    @abstractmethod
    async def search(self, embedding: list[float], versions: tuple,
                     keywords: list[str], top_k: int) -> list[dict]:
        """Search through this port."""
        raise NotImplementedError

    @abstractmethod
    async def upsert(self, texts: list[str], embeddings: list[list[float]],
                     metadata: list[dict]) -> None:
        """Upsert through this port."""
        raise NotImplementedError


class PatchNotes(Protocol):
    """Discover and extract patch notes."""

    @abstractmethod
    async def list(self) -> list[dict]:
        """List through this port."""
        raise NotImplementedError

    @abstractmethod
    async def chunks(self, version: str) -> list[dict] | None:
        """Chunks through this port."""
        raise NotImplementedError


class Assets(Protocol):
    """Enrich a detached match projection with DDragon spell and rune names."""

    @abstractmethod
    def enrich(self, match: Match) -> dict:
        """Enrich through this port."""
        raise NotImplementedError
