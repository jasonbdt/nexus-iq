"""Explicit aggregate relationships; ORM objects never cross this boundary."""
from dataclasses import fields
from datetime import datetime

from app.domain import models as domain
from app.domain.policies import aware
from . import models as tables

ENTITY_TYPES = {
    name: getattr(domain, name) for name in (
        'User', 'UserSummonerLink', 'Summoner', 'SummonerLeagues', 'Match',
        'MatchTeam', 'MatchTeamBans', 'MatchTeamObjectives', 'MatchParticipant',
        'MatchParticipantRunes', 'CoachSession', 'CoachMessage',
    )
}
CHILDREN = {
    'User': ('summoner_links',), 'Summoner': ('leagues',), 'Match': ('teams',),
    'MatchTeam': ('bans', 'objectives', 'participants'), 'MatchParticipant': ('runes',),
    'CoachSession': ('messages',),
}


def to_domain(row):
    """Materialize owned children and scalars while the session is open."""
    name = type(row).__name__
    children = CHILDREN.get(name, ())
    values = {}
    for attribute in fields(ENTITY_TYPES[name]):
        key = attribute.name
        if name == 'User' and key == 'role':
            role = row.role_links[0].role if row.role_links else None
            try:
                values[key] = domain.UserRole(role.name) if role else domain.UserRole.MEMBER
            except ValueError:
                values[key] = domain.UserRole.MEMBER
        elif key in children:
            values[key] = [to_domain(child) for child in getattr(row, key)]
        else:
            value = getattr(row, key)
            values[key] = aware(value) if isinstance(value, datetime) else value
    if name == 'User':
        values['summoner_links'].sort(key=lambda link: link.link_slot)
    if name == 'CoachSession':
        values['messages'].sort(key=lambda message: message.created_at)
    return ENTITY_TYPES[name](**values)


def scalar_row(entity, row=None):
    """Copy declared table columns, excluding relationships and application-only values."""
    table_type = getattr(tables, type(entity).__name__)
    values = {column.name: getattr(entity, column.name) for column in table_type.__table__.columns}
    if row is None:
        return table_type(**values)
    for key, value in values.items():
        setattr(row, key, value)
    return row
