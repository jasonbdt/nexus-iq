"""Optional Linux/RQ execution using an isolated Redis queue and fake upstream ports."""
from contextlib import asynccontextmanager
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest


@pytest.mark.skipif(os.name == 'nt' or os.getenv('NEXUS_TEST_REDIS') != '1',
                    reason='Requires the existing Linux worker image and Redis service')
def test_worker_job_path_executes_in_linux_rq_and_publishes_after_import(monkeypatch):
    from redis import Redis
    from rq import Queue, SimpleWorker
    from app.entrypoints import workers

    imported = AsyncMock(return_value=True)
    @asynccontextmanager
    async def runtime(**_kwargs):
        yield SimpleNamespace(players=SimpleNamespace(import_match=imported))
    monkeypatch.setattr(workers, 'open_services', runtime)
    identity = 'test-' + uuid4().hex
    connection = Redis(host=os.getenv('REDIS_HOST', 'redis'))
    queue = Queue('nexusiq-test-' + uuid4().hex, connection=connection)
    channel = 'nexus_iq:summoner_profile:' + identity
    key = 'nexus_iq:summoner_updates:' + identity
    pubsub = connection.pubsub()
    pubsub.subscribe(channel)
    pubsub.get_message(timeout=1)
    job = queue.enqueue('app.entrypoints.workers.persist_summoner_match_job',
                        args=(identity, 'euw', 'EUW1_TEST'))
    connection.sadd(key, job.id, 'other-pending-job')
    connection.set(key + ':total_jobs', 2)
    try:
        worker = SimpleWorker([queue], connection=connection, log_job_description=False)
        worker.work(burst=True, with_scheduler=False)
        job.refresh()
        assert job.is_finished
        imported.assert_awaited_once_with('euw', 'EUW1_TEST')
        updates = []
        for _ in range(4):
            message = pubsub.get_message(timeout=1)
            if message and message['type'] == 'message':
                updates.append(json.loads(message['data']))
        assert updates == [
            {'event': 'toggleUpdate', 'status': 'in_progress', 'progress': 50.0},
            {'event': 'reloadMatchList'},
        ]
    finally:
        pubsub.close()
        queue.delete(delete_jobs=True)
        job.delete()
        connection.delete(key, key + ':total_jobs')
        connection.close()
