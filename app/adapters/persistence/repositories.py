"""SQLModel repositories with flush-only writes and detached results."""
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.domain.errors import DuplicateUser
from . import models as tables
from .mapping import CHILDREN, scalar_row, to_domain


class Repository:
    """Common aggregate graph persistence; the owning UoW controls commit."""

    def __init__(self, session, table):
        self.session = session
        self.table = table

    def _one(self, statement):
        row = self.session.exec(statement).first()
        return to_domain(row) if row is not None else None

    def _all(self, statement):
        return [to_domain(row) for row in self.session.exec(statement).all()]

    def _save_graph(self, entity, parent_ids=None):
        parent_ids = parent_ids or {}
        for key, value in parent_ids.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        row_type = getattr(tables, type(entity).__name__)
        row = self.session.get(row_type, entity.id) if entity.id is not None else None
        row = scalar_row(entity, row)
        self.session.add(row)
        self.session.flush()
        entity.id = row.id
        owner = {
            'User': 'user_id', 'Summoner': 'summoner_id', 'Match': 'match_id',
            'MatchTeam': 'team_id', 'MatchParticipant': 'participant_id',
            'CoachSession': 'session_id',
        }.get(type(entity).__name__)
        child_ids = {**parent_ids, owner: row.id} if owner else parent_ids
        for relation in CHILDREN.get(type(entity).__name__, ()):
            kept = []
            for child in getattr(entity, relation):
                kept.append(self._save_graph(child, child_ids))
            for old in list(getattr(row, relation)):
                if old not in kept:
                    self.session.delete(old)
            setattr(row, relation, kept)
        self.session.flush()
        return row

    def save(self, entity):
        """Write a graph and return an independent snapshot, without committing."""
        return to_domain(self._save_graph(entity))

    def delete(self, entity):
        """Delete owned rows before their parent (the schema has no delete cascade)."""
        row = self.session.get(self.table, entity.id)
        self._delete_graph(row)

    def _delete_graph(self, row):
        for relation in CHILDREN.get(type(row).__name__, ()):
            for child in list(getattr(row, relation)):
                self._delete_graph(child)
        self.session.delete(row)
        self.session.flush()


class UsersRepository(Repository):
    """Persist users together with their role and account links."""

    def __init__(self, session):
        super().__init__(session, tables.User)

    def get(self, identity):
        """Find a user by database identity."""
        return self._one(select(self.table).where(self.table.id == identity))

    def by_email(self, email):
        """Find a user by the existing case-sensitive email lookup."""
        return self._one(select(self.table).where(self.table.emailAddress == email))

    def list(self, offset, limit):
        """List users using the existing pagination."""
        return self._all(select(self.table).offset(offset).limit(limit))

    def save(self, entity):
        """Ensure a default role assignment belongs to the same transaction."""
        try:
            row = self._save_graph(entity)
        except IntegrityError as error:
            # Translate only the existing email uniqueness constraint.
            if 'emailAddress' in str(error.orig):
                raise DuplicateUser('User already exists') from error
            raise
        if not row.role_links:
            role = self.session.exec(
                select(tables.Role).where(tables.Role.name == entity.role.value)
            ).first()
            if role is None:
                raise RuntimeError("Default 'member' role not found in roles table")
            row.role_links.append(tables.UserRoleLink(user_id=row.id, role_id=role.id))
            self.session.flush()
        return to_domain(row)

    def delete(self, entity):
        """Delete a user and its associations in a single transaction."""
        row = self.session.get(self.table, entity.id)
        for link in list(row.role_links):
            self.session.delete(link)
        # Coaching has a foreign key to users but is not part of the user aggregate.
        coaching = CoachingRepository(self.session)
        for conversation in coaching.list(entity.id):
            coaching.delete(conversation)
        super().delete(entity)


class SummonersRepository(Repository):
    """Cached profiles including stable ranked-queue row identities."""

    def __init__(self, session):
        super().__init__(session, tables.Summoner)

    def get(self, puuid):
        """Find a profile by Riot's stable identity."""
        return self._one(select(self.table).where(self.table.puuid == puuid))

    def by_name(self, game_name, tag_line):
        """Find a profile by its current display name."""
        return self._one(select(self.table).where(
            self.table.summoner_name == game_name.strip(),
            self.table.tag_line == tag_line.strip(),
        ))


class MatchesRepository(Repository):
    """Store and read a complete immutable imported match."""

    def __init__(self, session):
        super().__init__(session, tables.Match)

    def get(self, match_id):
        """Find a match by Riot match ID."""
        return self._one(select(self.table).where(self.table.match_id == match_id))

    def recent(self, puuid, count):
        """Return the same descending match history without lazy ORM values."""
        statement = select(self.table).join(tables.MatchParticipant).where(
            tables.MatchParticipant.summoner_puuid == puuid,
        ).order_by(desc(self.table.game_end)).limit(count)
        return self._all(statement)


class CoachingRepository(Repository):
    """User-owned conversations and messages."""

    def __init__(self, session):
        super().__init__(session, tables.CoachSession)

    def get(self, identity):
        """Find a conversation by identity."""
        return self._one(select(self.table).where(self.table.id == identity))

    def list(self, user_id):
        """Return a user's conversations, newest first."""
        return self._all(select(self.table).where(self.table.user_id == user_id)
                         .order_by(desc(self.table.updated_at)))
