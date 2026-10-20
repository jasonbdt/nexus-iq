"""Pure business and application tests, without SQLModel, FastAPI or external services."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.domain.errors import Forbidden, InvalidOperation
from app.domain.models import User, UserRole, UserSummonerLink, Summoner, utc_now
from app.domain.policies import check_link, ttl_expired, resolved_question
from app.service_layer.accounts import Accounts
from app.service_layer.coaching import Coaching
from app.service_layer.rag import Retrieval
from tests.fakes import MemoryStore


@pytest.mark.parametrize('role', list(UserRole))
def test_premium_slot_policy(role):
    user = User(avatarName='Test', emailAddress='test@test.com', password='hash', role=role)
    if role == UserRole.MEMBER:
        with pytest.raises(Forbidden):
            check_link(user, 1, utc_now())
    else:
        check_link(user, 1, utc_now())
        user.summoner_links = [UserSummonerLink(user_id=1, link_slot=slot,
                                               summoner_puuid='p' * 78) for slot in (1, 2)]
        with pytest.raises(InvalidOperation, match='Maximum 2'):
            check_link(user, 2, utc_now())


def test_cooldown_and_ttl_boundaries():
    now = utc_now()
    user = User(avatarName='Test', emailAddress='test@test.com', password='hash')
    user.summoner_links.append(UserSummonerLink(user_id=1, link_slot=0, summoner_puuid='p' * 78,
                                               linked_at=now - timedelta(days=29)))
    with pytest.raises(InvalidOperation, match='1 days'):
        check_link(user, 0, now)
    check_link(user, 0, now + timedelta(days=1))
    summoner = Summoner(puuid='p' * 78, region='euw', summoner_name='Player', tag_line='EUW',
                        summoner_level=1, profile_icon=1, revision_date=now, updated_at=now)
    assert not ttl_expired(summoner, now + timedelta(seconds=29), 0.5)
    assert ttl_expired(summoner, now + timedelta(seconds=30), 0.5)


async def test_registration_uses_only_application_ports():
    store = MemoryStore()
    now = utc_now()
    incoming = Summoner(puuid='p' * 78, region='euw', summoner_name='Player', tag_line='EUW',
                        summoner_level=1, profile_icon=1, revision_date=now)
    async def profile(*_args):
        assert store.active == 0
        return incoming
    accounts = Accounts(store, SimpleNamespace(profile=profile),
                        SimpleNamespace(hash_password=lambda _plain: 'hash'))
    result = await accounts.register({'emailAddress': 'test@test.com', 'password': 'plain',
                                     'password_confirm': 'plain', 'gameName': 'Player',
                                     'tagLine': 'EUW'})
    assert result['avatarName'] == 'Player#EUW'
    assert result['role'] == UserRole.MEMBER
    assert 'password' not in result
    assert store.commits == 1


async def test_coaching_transactions_finish_before_context_and_stream():
    store = MemoryStore()
    def stream(*_args):
        assert store.active == 0
        yield 'complete'
        assert store.active == 0
    ai = SimpleNamespace(versions=Mock(return_value=(0, 26.4)), keywords=Mock(return_value=[]),
                         embed=AsyncMock(return_value=[1.0]), stream=stream)
    vectors = SimpleNamespace(search=AsyncMock(return_value=[]))
    retrieval = Retrieval(ai, vectors, SimpleNamespace())
    coaching = Coaching(store, retrieval)
    conversation = coaching.create(1, 'New Session')
    iterator = await coaching.chat(conversation.id, 1, 'Question')
    assert store.active == 0
    assert list(iterator) == ['complete']
    assert store.commits == 3
    assert [item.role for item in coaching.get(conversation.id, 1).messages] == ['user', 'assistant']
    history = [{'role': 'user', 'content': str(index)} for index in range(10)]
    resolved = resolved_question('Follow-up', history)
    assert 'User: 3\n' not in resolved
    assert resolved.endswith('User: 9\nUser: Follow-up')
