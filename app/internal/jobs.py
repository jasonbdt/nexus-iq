"""
Background tasks for asynchronous job execution.

This module defines worker jobs and supporting helpers that run outside the
regular request-response flow. It serves as the central place for background
processing logic such as external API synchronization, database persistence,
job orchestration, progress tracking, and Pub/Sub notifications.
"""
import json
import os
import time

import aiohttp
from redis import Redis
from sqlmodel import Session
from rq import Queue, Retry, get_current_job
from rq.group import Group

from .controllers import summoners as SummonersController
from .db import engine
from .session import init_session
from .riot_api import get_riot_api, get_riot_api_config


timeout = aiohttp.ClientTimeout(total=10)
headers = {"X-Riot-Token": os.getenv("RIOT_API_KEY")}


async def update_summoner_profile_job(
    puuid: str
) -> None:
    """
    Refreshes the persisted summoner profile as part of a background
    update job.

    This worker task initializes the Riot API client, loads the current
    RQ job context, and updates the summoner profile in the database for
    the given PUUID. After the profile refresh has completed, the job
    removes itself from the Redis set of pending update jobs and
    publishes an updated progress event for the summoner-specific
    Pub/Sub channel.

    Args:
        puuid: The encrypted Riot PUUID of the summoner to refresh.

    Returns:
        None
    """
    job = get_current_job()
    redis_conn = job.connection

    connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
    await init_session(timeout=timeout, connector=connector, headers=headers)
    riot_api = get_riot_api(get_riot_api_config())

    with Session(engine) as session:
        await SummonersController.refresh_summoner_profile(puuid, session, riot_api)
        redis_conn.srem(f"nexus_iq:summoner_updates:{puuid}", job.id)
        redis_conn.publish(f"nexus_iq:summoner_profile:{puuid}", message=json.dumps({
            "event": "toggleUpdate",
            "status": "in_progress",
            "progress": calc_update_progress(puuid, redis_conn)
        }))


def reset_summoner_status(puuid: str, redis_conn: Redis):
    """
    Publishes the final status transition for a completed
    summoner update.

    This helper notifies subscribers that the summoner update has
    finished by first publishing a ``finished`` event with full progress
    and then, after a short delay, resetting the status back to
    ``idle``. This allows clients to briefly display the completed state
    before returning to the default idle state.

    Args:
        puuid: The encrypted Riot PUUID of the summoner whose update
               status should be reset.
        redis_conn: The Redis connection used to publish status events.

    Returns:
        None
    """
    redis_conn.publish(
        f"nexus_iq:summoner_profile:{puuid}",
        message=json.dumps({
            "event": "toggleUpdate",
            "status": "finished",
            "progress": 100.00,
        })
    )
    time.sleep(1)
    redis_conn.publish(
        f"nexus_iq:summoner_profile:{puuid}",
        message=json.dumps({
            "event": "toggleUpdate",
            "status": "idle",
            "progress": 0.00
        })
    )


async def persist_summoner_match_job(
    puuid: str,
    region: str,
    match_id: str
) -> None:
    """
    Persists a single summoner match and updates the overall
    sync progress.

    This worker task initializes the Riot API client and stores the
    specified match in the database for the given summoner context.
    After execution, the current job removes itself from the Redis set
    of pending update jobs regardless of success or failure.

    If additional update jobs are still pending, the function publishes
    an ``in_progress`` event with the recalculated progress. If no jobs
    remain, it publishes the final status transition by resetting the
    summoner update state.

    Args:
        puuid: The encrypted Riot PUUID of the summoner whose update is
               being processed.
        region: The Riot routing value required to load the match data.
        match_id: The Riot match ID to persist.

    Returns:
        None
    """
    job = get_current_job()
    redis_conn = job.connection

    connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
    await init_session(timeout=timeout, connector=connector, headers=headers)
    riot_api = get_riot_api(get_riot_api_config())

    try:
        with Session(engine) as session:
            await SummonersController.persist_summoner_match(
                region, match_id, session, riot_api
            )
    finally:
        redis_conn.srem(f"nexus_iq:summoner_updates:{puuid}", job.id)
        remaining_jobs = int(redis_conn.scard(f"nexus_iq:summoner_updates:{puuid}") or 0)

        if remaining_jobs > 0:
            redis_conn.publish(f"nexus_iq:summoner_profile:{puuid}", message=json.dumps({
                "event": "toggleUpdate",
                "status": "in_progress",
                "progress": calc_update_progress(puuid, redis_conn)
            }))
        else:
            reset_summoner_status(puuid, redis_conn)


async def sync_summoner_matches_job(
    puuid: str,
    match_count: int,
):
    """
    Finds missing recent matches for a summoner and enqueues
    persistence jobs.

    This worker task loads the summoner from the database, fetches
    recent match IDs from the Riot API, filters out matches that already
    exist locally, and creates one background job per new match to
    persist the missing data.

    If the summoner does not exist or no new matches are found, the
    function stops early. In the no-op case, it also removes the current
    job from the Redis set of pending update jobs and resets the
    summoner status to its completed state.

    For newly discovered matches, the function enqueues grouped
    follow-up jobs with retry behavior, removes the current sync job
    from the pending set, and updates the Redis-based job tracking state
    so progress can be calculated correctly by subsequent workers.

    Args:
        puuid: The encrypted Riot PUUID of the summoner whose recent
               matches should be synchronized.
        match_count: The maximum number of recent matches to inspect.

    Returns:
        list[str] | None: A list of newly discovered match IDs if
                          follow-up jobs were enqueued, otherwise
                          ``None``.
    """
    job = get_current_job()
    redis_conn = job.connection

    connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
    await init_session(timeout=timeout, connector=connector, headers=headers)
    riot_api = get_riot_api(get_riot_api_config())

    with Session(engine) as session:
        summoner = SummonersController.get_summoner_by_puuid(puuid, session)
        if not summoner:
            return None

        match_ids = await riot_api.get_recent_match_ids(
            summoner.puuid, summoner.region, match_count
        )
        new_match_ids = [
            match_id for match_id in reversed(match_ids)
            if not SummonersController.get_match_by_match_id(match_id, session)
        ]

        if not new_match_ids:
            redis_conn.srem(f"nexus_iq:summoner_updates:{puuid}", job.id)
            reset_summoner_status(puuid, redis_conn)
            return None

        queue = Queue("default", connection=redis_conn)
        retry = Retry(max=3, interval=[30, 60, 120])

        group = Group.create(connection=redis_conn)
        group.enqueue_many(
            queue=queue,
            job_datas=[
                Queue.prepare_data(
                    persist_summoner_match_job,
                    args=(puuid, summoner.region, match_id),
                    timeout=300,
                    retry=retry
                ) for match_id in new_match_ids
            ]
        )

        job_ids = [jobs.id for jobs in group.get_jobs()]
        redis_conn.srem(f"nexus_iq:summoner_updates:{puuid}", job.id)

        for job_id in job_ids:
            redis_conn.incr(f"nexus_iq:summoner_updates:{puuid}:total_jobs")
            redis_conn.sadd(f"nexus_iq:summoner_updates:{puuid}", job_id)

        return new_match_ids


def enqueue_summoner_update(
    puuid: str,
    match_count: int = 20,
) -> None:
    """Enqueues summoner update for worker daemons."""
    redis_conn = Redis(host=os.getenv("REDIS_HOST"))
    queue = Queue("default", connection=redis_conn)

    update_profile_job = queue.enqueue(
        update_summoner_profile_job,
        args=(puuid,)
    )
    fetch_matches_job = queue.enqueue(
        sync_summoner_matches_job,
        args=(puuid, match_count),
        depends_on=update_profile_job
    )

    job_ids = [update_profile_job.id, fetch_matches_job.id]

    redis_conn.set(f"nexus_iq:summoner_updates:{puuid}:total_jobs", 0)
    for job_id in job_ids:
        redis_conn.incr(f"nexus_iq:summoner_updates:{puuid}:total_jobs")
        redis_conn.sadd(f"nexus_iq:summoner_updates:{puuid}", job_id)

    redis_conn.publish(f"nexus_iq:summoner_profile:{puuid}", message=json.dumps({
        "event": "toggleUpdate",
        "status": "queued",
        "progress": 0.00
    }))


def calc_update_progress(puuid: str, redis_conn: Redis) -> float:
    """
    Calculates the current progress percentage for a summoner update.

    This helper derives update progress from the Redis-based job
    tracking state by comparing the number of remaining jobs with the
    total number of registered jobs for the summoner.

    When no jobs remain, the stored total job counter is removed from
    Redis as part of the cleanup.

    Args:
        puuid: The encrypted Riot PUUID of the summoner whose update
               progress should be calculated.
        redis_conn: The Redis connection used to read and clean up
                    job metadata.

    Returns:
        float: The current update progress as a percentage with two
               decimal places.
    """
    channel = "nexus_iq:summoner_updates"
    remaining_jobs = int(
        redis_conn.scard(f"{channel}:{puuid}")
    )
    total_jobs = int(
        redis_conn.get(f"{channel}:{puuid}:total_jobs")
        or 0
    )

    if remaining_jobs == 0:
        redis_conn.delete(f"{channel}:{puuid}:total_jobs")

    return float(f"{(1 - (remaining_jobs / total_jobs)) * 100:.2f}")
