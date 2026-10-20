"""Every acquired resource is closed even if application initialization fails."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app import bootstrap


async def test_startup_failure_closes_all_resources(monkeypatch):
    engine = SimpleNamespace(dispose=Mock())
    redis = SimpleNamespace(aclose=AsyncMock())
    http = SimpleNamespace()
    class HttpContext:
        async def __aenter__(self):
            return http
        async def __aexit__(self, *_args):
            http.closed = True
    ai = SimpleNamespace(close=Mock())
    qdrant = SimpleNamespace(close=AsyncMock())
    store = SimpleNamespace(ensure_collection=AsyncMock(side_effect=RuntimeError('startup failed')))
    settings = SimpleNamespace(
        app_env='test', database_url='unused', redis_host='unused', riot_key='test',
        jwt_secret='test', jwt_minutes=60, openai_key='test', qdrant_host='unused',
        qdrant_port=6333, collection='test', dimension=1,
        namespace='12345678-1234-5678-1234-567812345678', top_k=5,
    )
    monkeypatch.setattr(bootstrap, 'create_engine', lambda *_: engine)
    monkeypatch.setattr(bootstrap, 'Redis', lambda **_: redis)
    monkeypatch.setattr(bootstrap.aiohttp, 'ClientSession', lambda **_: HttpContext())
    monkeypatch.setattr(bootstrap, 'OpenAI', lambda **_: ai)
    monkeypatch.setattr(bootstrap, 'AsyncQdrantClient', lambda **_: qdrant)
    monkeypatch.setattr(bootstrap, 'VectorStore', lambda *_args, **_kwargs: store)
    monkeypatch.setattr(bootstrap, 'ensure_ddragon_cached_sync', lambda: None)
    with pytest.raises(RuntimeError, match='startup failed'):
        async with bootstrap.open_services(settings):
            raise AssertionError('startup should fail before yielding')
    assert http.closed
    engine.dispose.assert_called_once()
    redis.aclose.assert_awaited_once()
    ai.close.assert_called_once()
    qdrant.close.assert_awaited_once()
