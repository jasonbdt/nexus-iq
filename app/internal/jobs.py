from rq.job import Job


async def summoner_update_job(
    puuid: str,
    match_count: int = 20
) -> None:
    import os

    import aiohttp
    from sqlmodel import Session

    from .controllers import summoners as SummonersController
    from .db import engine
    from .session import init_session
    from .riot_api import get_riot_api, get_riot_api_config

    timeout = aiohttp.ClientTimeout(total=10)
    headers = {"X-Riot-Token": os.getenv("RIOT_API_KEY")}
    connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)

    await init_session(timeout=timeout, connector=connector, headers=headers)
    riot_api = get_riot_api(get_riot_api_config())

    with Session(engine) as session:
        await SummonersController.find_and_update(puuid, session, riot_api, match_count)


def enqueue_summoner_update(
    redis_conn,
    puuid: str,
    match_count: int = 20
) -> Job:
    from rq import Queue
    queue = Queue("default", connection=redis_conn)
    return queue.enqueue(summoner_update_job, puuid, match_count, job_timeout="15m")
