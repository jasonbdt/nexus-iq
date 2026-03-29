import os

import aiohttp
from redis import Redis
from sqlmodel import Session
from rq import Queue, Retry
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
    from rq import get_current_job
    job = get_current_job()
    redis_conn = job.connection

    connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
    await init_session(timeout=timeout, connector=connector, headers=headers)
    riot_api = get_riot_api(get_riot_api_config())

    with Session(engine) as session:
        await SummonersController.refresh_summoner_profile(puuid, session, riot_api)
        redis_conn.srem(f"nexus_iq:summoner_updates:{puuid}", job.id)




async def persist_summoner_match_job(
    puuid: str,
    region: str,
    match_id: str
) -> None:
    from rq import get_current_job
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


async def sync_summoner_matches_job(
    puuid: str,
    match_count: int,
):
    from rq import get_current_job
    job = get_current_job()
    redis_conn = job.connection

    connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
    await init_session(timeout=timeout, connector=connector, headers=headers)
    riot_api = get_riot_api(get_riot_api_config())

    with Session(engine) as session:
        summoner = SummonersController.get_summoner_by_puuid(puuid, session)
        if not summoner:
            return None

        match_ids = await riot_api.get_recent_match_ids(summoner.puuid, summoner.region, match_count)
        new_match_ids = [
            match_id for match_id in reversed(match_ids)
            if not SummonersController.get_match_by_match_id(match_id, session)
        ]

        if not new_match_ids:
            redis_conn.srem(f"nexus_iq:summoner_updates:{puuid}", job.id)
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
    from redis import Redis
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

