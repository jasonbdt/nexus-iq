"""Contracts consumed by Angular: authentication, REST, named events and token streams."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.domain.models import User, UserRole
from app.entrypoints.http.sse import build_sse, parse_pubsub_message, token_events
from tests.factories import active_user


def test_login_profile_authorization_and_queued_response(client, services):
    user, headers = active_user(services)
    response = client.post('/login', data={'username': user.emailAddress, 'password': 'password'})
    assert response.status_code == 200
    assert set(response.json()) == {'access_token', 'token_type'}
    assert response.json()['token_type'] == 'bearer'
    profile = client.get('/users/me', headers=headers)
    assert profile.status_code == 200
    assert set(profile.json()) == {
        'avatarName', 'emailAddress', 'is_active', 'role', 'created_at', 'updated_at',
        'linked_summoner', 'summoner_linked_at', 'additional_summoners', 'language',
        'subscription_tier',
    }
    assert client.get('/users/me').status_code == 401
    assert client.get('/users', headers=headers).status_code == 403
    assert client.get('/users?limit=101', headers=headers).status_code == 403
    invalid = client.get('/users/me', headers={'Authorization': 'Bearer invalid'})
    assert invalid.status_code == 401
    assert invalid.headers['www-authenticate'] == 'Bearer'
    queued = client.patch('/update/' + 'p' * 78 + '?match_count=12', headers=headers)
    assert queued.json() == {'message': 'Update queued'}
    services.updates.enqueue.assert_called_once_with('p' * 78, 12)


def test_search_null_omission_not_found_and_optional_credentials(client, services):
    response = client.get('/search/EUW/Player', headers={'Authorization': 'Bearer invalid'})
    assert response.status_code == 200
    assert response.json()['status'] == 'idle'
    assert response.json()['leagues'] == []
    assert 'update_progress' not in response.json()
    services.players.riot.profile.return_value = None
    missing = client.get('/search/OTHER/DoesNotExist')
    assert missing.status_code == 404
    assert missing.json() == {'message': 'Summoner not found'}


def test_inactive_login_and_user_management_contracts(client, services):
    with services.accounts.uow() as work:
        inactive = work.users.save(User(avatarName='Inactive', emailAddress='inactive@test.com',
                                       password=services.accounts.security.hash_password('pass')))
        admin = work.users.save(User(avatarName='Admin', emailAddress='admin@test.com',
                                    password='unused', is_active=True, role=UserRole.ADMINISTRATOR))
        work.commit()
    login = client.post('/login', data={'username': inactive.emailAddress, 'password': 'pass'})
    assert login.status_code == 200
    response = client.get('/users/me', headers={
        'Authorization': 'Bearer ' + login.json()['access_token'],
    })
    assert response.status_code == 400
    assert response.json() == {'detail': 'Inactive User'}
    headers = {'Authorization': 'Bearer ' + services.accounts.security.token(admin.emailAddress,
                                                                            admin.role.value)}
    assert len(client.get('/users?limit=1', headers=headers).json()['users']) == 1
    assert client.get('/users?limit=101', headers=headers).status_code == 422
    assert client.patch('/users/me', json={}, headers=headers).json() == {
        'detail': 'No fields to update',
    }
    update = client.patch('/users/me', json={'language': 'de'}, headers=headers)
    assert update.status_code == 200
    assert update.json()['language'] == 'de'
    assert client.delete('/users/' + str(inactive.id), headers=headers).json() == {
        'status': 200, 'message': 'Success',
    }


def test_coaching_crud_history_ownership_and_sse_contract(client, services):
    user, headers = active_user(services)
    created = client.post('/coach/sessions', json={}, headers=headers)
    assert created.status_code == 201
    identity = created.json()['id']
    assert created.json()['messages'] == []
    assert client.get('/coach/sessions', headers=headers).json()[0]['id'] == identity
    streamed = client.post(f'/coach/sessions/{identity}/chat?question=Question', headers=headers)
    assert streamed.status_code == 200
    assert streamed.headers['content-type'].startswith('text/event-stream')
    assert streamed.headers['x-accel-buffering'] == 'no'
    assert streamed.text == 'data: {"delta": "Hello"}\n\ndata: {"delta": " world"}\n\ndata: [DONE]\n\n'
    saved = client.get(f'/coach/sessions/{identity}', headers=headers).json()
    assert saved['title'] == 'Question'
    assert [(message['role'], message['content']) for message in saved['messages']] == [
        ('user', 'Question'), ('assistant', 'Hello world'),
    ]
    renamed = client.patch(f'/coach/sessions/{identity}', json={'title': 'Renamed'}, headers=headers)
    assert renamed.json()['title'] == 'Renamed'
    assert renamed.json()['messages'] == []
    _, stranger = active_user(services, 'stranger@test.com')
    assert client.get(f'/coach/sessions/{identity}', headers=stranger).status_code == 404
    deleted = client.delete(f'/coach/sessions/{identity}', headers=headers)
    assert deleted.status_code == 204
    assert deleted.content == b''
    assert client.get(f'/coach/sessions/{identity}', headers=headers).status_code == 404


async def test_aborted_chat_closes_sdk_without_persisting_partial_answer(services):
    user, _ = active_user(services)
    conversation = services.coaching.create(user.id, 'New Session')
    closed = []
    def tokens(*_):
        try:
            yield 'partial'
            yield 'rest'
        finally:
            closed.append(True)
    services.retrieval.ai.stream.side_effect = tokens
    stream = await services.coaching.chat(conversation.id, user.id, 'Question')
    assert next(stream) == 'partial'
    stream.close()
    assert closed == [True]
    saved = services.coaching.get(conversation.id, user.id)
    assert [(message.role, message.content) for message in saved.messages] == [('user', 'Question')]


async def test_failed_stream_has_no_done_and_no_partial_assistant(services):
    user, _ = active_user(services)
    conversation = services.coaching.create(user.id, 'New Session')
    def tokens(*_):
        yield 'partial'
        raise RuntimeError('SDK failed')
    services.retrieval.ai.stream.side_effect = tokens
    iterator = await services.coaching.chat(conversation.id, user.id, 'Question')
    events = []
    with pytest.raises(RuntimeError, match='SDK failed'):
        async for event in token_events(iterator):
            events.append(event)
    assert events == ['data: {"delta": "partial"}\n\n']
    assert len(services.coaching.get(conversation.id, user.id).messages) == 1


def test_rag_query_ingestion_and_stream_shapes(client, services):
    assert client.post('/query?question=Question&top_k=3').json() == {'message': 'Answer'}
    services.retrieval.vectors.search.assert_awaited_with([0.1], (0.0, 26.4), [], 3)
    streamed = client.post('/query/stream?question=Question')
    assert streamed.text.endswith('data: [DONE]\n\n')
    assert client.get('/patches').json() == {'patches': []}
    assert client.post('/ingest/26.4').status_code == 400
    services.retrieval.patches.chunks.return_value = [
        {'text': 'Patch', 'source': 'https://example.test', 'chunk_index': 0},
    ]
    assert client.post('/ingest/invalid').status_code == 422
    response = client.post('/ingest/26.4')
    assert response.json() == {'message': 'Patch Notes for v26.4 ingested successfully', 'count': 1}


@pytest.mark.parametrize('payload,event,data', [
    (b'{"event":"toggleUpdate","status":"queued","progress":0}', 'toggleUpdate',
     {'status': 'queued', 'progress': 0}),
    ({'event': 'reloadMatchList'}, 'reloadMatchList', {}),
    ({'event': 'update', 'payload': {'x': 1}}, 'update', {'x': 1}),
    ('plain text', 'update', 'plain text'),
])
def test_named_update_wire_format(payload, event, data):
    assert parse_pubsub_message(payload) == (event, data)
    expected = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    assert build_sse(data, event=event) == f'event: {event}\ndata: {expected}\n\n'


async def test_subscription_adapter_releases_pubsub_on_close():
    from app.adapters.updates import UpdateGateway
    pubsub = SimpleNamespace(subscribe=AsyncMock(), unsubscribe=AsyncMock(), aclose=AsyncMock(),
                             get_message=AsyncMock(return_value=None))
    client = SimpleNamespace(pubsub=lambda **_: pubsub)
    stream = UpdateGateway(client, 'unused').subscribe('player')
    assert await anext(stream) is None
    await stream.aclose()
    pubsub.subscribe.assert_awaited_once_with('nexus_iq:summoner_profile:player')
    pubsub.unsubscribe.assert_awaited_once_with('nexus_iq:summoner_profile:player')
    pubsub.aclose.assert_awaited_once()
