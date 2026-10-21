"""Regression coverage for partial writes, mapper round trips and transaction ownership."""
from dataclasses import is_dataclass

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.domain.errors import DuplicateUser
from app.domain.models import User
from app.adapters.persistence import models as tables
from app.adapters.persistence.repositories import Repository, UsersRepository
from tests.factories import match, riot_match


def registration():
    return {'emailAddress': 'new@example.test', 'password': 'password',
            'password_confirm': 'password', 'gameName': 'Player', 'tagLine': 'EUW'}


def test_registration_not_found_leaves_no_user(client, services, db_session):
    services.accounts.riot.profile.return_value = None
    response = client.post('/register', json=registration())
    assert response.status_code == 404
    assert response.json() == {'detail': 'Player account not found. Check the name and tag.'}
    assert db_session.exec(select(tables.User)).all() == []


def test_registration_rolls_back_after_every_association_was_flushed(
    app_no_lifespan, monkeypatch, db_session,
):
    original = UsersRepository.save
    def fail_after_save(repository, user):
        original(repository, user)
        raise RuntimeError('failure after user, profile, link and role were written')
    monkeypatch.setattr(UsersRepository, 'save', fail_after_save)
    response = TestClient(app_no_lifespan, raise_server_exceptions=False).post(
        '/register', json=registration(),
    )
    assert response.status_code == 500
    for table in (tables.User, tables.UserRoleLink, tables.UserSummonerLink, tables.Summoner):
        assert db_session.exec(select(table)).all() == []


async def test_match_import_rolls_back_complete_graph_on_late_failure(
    services, monkeypatch, db_session,
):
    services.players.riot.match.return_value = match()
    original = Repository._save_graph
    def fail_on_runes(repository, entity, parent_ids=None):
        if type(entity).__name__ == 'MatchParticipantRunes':
            raise RuntimeError('runes failed after match, team and participant were flushed')
        return original(repository, entity, parent_ids)
    monkeypatch.setattr(Repository, '_save_graph', fail_on_runes)
    with pytest.raises(RuntimeError, match='runes failed'):
        await services.players.import_match('euw', 'EUW1_123')
    for table in (tables.Match, tables.MatchTeam, tables.MatchTeamBans, tables.MatchTeamObjectives,
                  tables.MatchParticipant, tables.MatchParticipantRunes):
        assert db_session.exec(select(table)).all() == []


async def test_match_import_is_complete_detached_and_idempotent(services, db_session):
    services.players.riot.match.return_value = match()
    assert await services.players.import_match('euw', 'EUW1_123')
    assert not await services.players.import_match('euw', 'EUW1_123')
    services.players.riot.match.assert_awaited_once()
    with services.players.uow() as work:
        result = work.matches.get('EUW1_123')
    assert is_dataclass(result)
    assert len(result.teams) == 2
    assert len(result.teams[0].participants) == 2
    assert result.teams[0].participants[0].runes[0].primary_style == 8000
    assert len(db_session.exec(select(tables.MatchParticipant)).all()) == 3
    for participant in db_session.exec(select(tables.MatchParticipant)).all():
        assert participant.match_id == result.id
        assert participant.team.match_id == result.id


def test_uow_rolls_back_by_default_and_translates_duplicate_email(services, db_session):
    with services.accounts.uow() as work:
        work.users.save(User(avatarName='Test', emailAddress='same@test.com', password='hash'))
    assert db_session.exec(select(tables.User)).all() == []
    with services.accounts.uow() as work:
        work.users.save(User(avatarName='Test', emailAddress='same@test.com', password='hash'))
        work.commit()
    with pytest.raises(DuplicateUser, match='User already exists'):
        with services.accounts.uow() as work:
            work.users.save(User(avatarName='Other', emailAddress='same@test.com', password='hash'))
    assert len(db_session.exec(select(tables.User)).all()) == 1


def test_riot_transport_mapping_retains_identity_and_all_owned_rows(services):
    from app.adapters.riot import match_entity
    incoming = match_entity(riot_match())
    assert incoming.match_id == 'EUW1_123'
    with services.players.uow() as work:
        work.matches.save(incoming)
        work.commit()
    with services.players.uow() as work:
        saved = work.matches.get('EUW1_123')
    assert saved.teams[0].team_id == 100
    assert saved.teams[1].team_id == 200
    assert saved.teams[0].bans[0].champion_id == 2
    assert saved.teams[0].objectives[0].objective == 'baron'
    assert saved.teams[0].participants[0].runes[0].primary_style == 8000
