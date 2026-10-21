"""Thin RQ entrypoints that invoke the same player use cases as HTTP."""
from rq import get_current_job

from app.bootstrap import open_services
from app.adapters.rq_queue import enqueue_matches, finish, progress, publish


async def update_summoner_profile_job(puuid: str) -> None:
    """Refresh and commit a profile before notifying subscribers."""
    job = get_current_job()
    async with open_services(worker=True) as services:
        await services.players.refresh(puuid)
    connection = job.connection
    connection.srem(f'nexus_iq:summoner_updates:{puuid}', job.id)
    publish(connection, puuid, event='toggleUpdate', status='in_progress',
            progress=progress(puuid, connection))


async def persist_summoner_match_job(puuid: str, region: str, match_id: str) -> None:
    """Import atomically, preserving retry failures without announcing uncommitted data."""
    job = get_current_job()
    connection = job.connection
    imported = False
    try:
        async with open_services(worker=True) as services:
            imported = await services.players.import_match(region, match_id)
    finally:
        key = f'nexus_iq:summoner_updates:{puuid}'
        connection.srem(key, job.id)
        if int(connection.scard(key) or 0) > 0:
            publish(connection, puuid, event='toggleUpdate', status='in_progress',
                    progress=progress(puuid, connection))
            if imported:
                publish(connection, puuid, event='reloadMatchList')
        else:
            finish(puuid, connection)


async def sync_summoner_matches_job(puuid: str, match_count: int):
    """Discover missing matches, then delegate grouped scheduling to the RQ adapter."""
    job = get_current_job()
    connection = job.connection
    async with open_services(worker=True) as services:
        result = await services.players.missing_matches(puuid, match_count)
    key = f'nexus_iq:summoner_updates:{puuid}'
    if result is None or not result[1]:
        connection.srem(key, job.id)
        finish(puuid, connection)
        return None
    region, match_ids = result
    enqueue_matches(connection, puuid, region, match_ids)
    connection.srem(key, job.id)
    return match_ids
