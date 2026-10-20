"""RQ orchestration and existing Redis progress protocol (Linux runtime)."""
import json
import time

from redis import Redis
from rq import Queue, Retry
from rq.group import Group


def progress(puuid: str, connection: Redis) -> float:
    """Compute the existing two-decimal progress, including an empty batch."""
    key = f'nexus_iq:summoner_updates:{puuid}'
    remaining = int(connection.scard(key))
    total = int(connection.get(f'{key}:total_jobs') or 0)
    if remaining == 0:
        connection.delete(f'{key}:total_jobs')
    return round((1 - remaining / total) * 100, 2) if total else 0.0


def publish(connection: Redis, puuid: str, **payload) -> None:
    """Publish the unchanged player-profile notification format."""
    connection.publish(f'nexus_iq:summoner_profile:{puuid}', message=json.dumps(payload))


def finish(puuid: str, connection: Redis) -> None:
    """Preserve the finished-to-idle transition and its brief display interval."""
    publish(connection, puuid, event='toggleUpdate', status='finished', progress=100.0)
    time.sleep(1)
    publish(connection, puuid, event='toggleUpdate', status='idle', progress=0.0)


def enqueue_update(host: str, puuid: str, count: int = 20) -> None:
    """Queue the profile refresh before match discovery, preserving dependencies."""
    with Redis(host=host) as connection:
        queue = Queue('default', connection=connection)
        profile_job = queue.enqueue('app.entrypoints.workers.update_summoner_profile_job', args=(puuid,))
        matches_job = queue.enqueue('app.entrypoints.workers.sync_summoner_matches_job',
                                    args=(puuid, count), depends_on=profile_job)
        key = f'nexus_iq:summoner_updates:{puuid}'
        connection.set(f'{key}:total_jobs', 0)
        for job in (profile_job, matches_job):
            connection.incr(f'{key}:total_jobs')
            connection.sadd(key, job.id)
        publish(connection, puuid, event='toggleUpdate', status='queued', progress=0.0)


def enqueue_matches(connection: Redis, puuid: str, region: str, match_ids: list[str]) -> None:
    """Keep grouped match jobs and their existing retry delays and timeout."""
    queue = Queue('default', connection=connection)
    group = Group.create(connection=connection)
    group.enqueue_many(queue=queue, job_datas=[Queue.prepare_data(
        'app.entrypoints.workers.persist_summoner_match_job', args=(puuid, region, match_id), timeout=300,
        retry=Retry(max=3, interval=[30, 60, 120]),
    ) for match_id in match_ids])
    key = f'nexus_iq:summoner_updates:{puuid}'
    for job in group.get_jobs():
        connection.incr(f'{key}:total_jobs')
        connection.sadd(key, job.id)
