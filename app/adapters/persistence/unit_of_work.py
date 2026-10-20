"""One session per unit of work, explicit commits and rollback by default."""
from .repositories import (
    UsersRepository, SummonersRepository, MatchesRepository, CoachingRepository,
)


class SqlUnitOfWork:
    """Own the session lifecycle and transaction for a single operation."""

    def __init__(self, session_factory):
        self._session_factory = session_factory
        self.session = None
        self.users = None
        self.summoners = None
        self.matches = None
        self.coaching = None

    def __enter__(self):
        self.session = self._session_factory()
        self.users = UsersRepository(self.session)
        self.summoners = SummonersRepository(self.session)
        self.matches = MatchesRepository(self.session)
        self.coaching = CoachingRepository(self.session)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.rollback()
        finally:
            self.session.close()

    def commit(self):
        """Persist every repository write together."""
        self.session.commit()

    def rollback(self):
        """Discard uncommitted changes, also on a normal context exit."""
        self.session.rollback()
