"""Redis progress reads and subscriptions; RQ is imported only when queueing."""
import asyncio
from contextlib import suppress
from anyio import CancelScope


class UpdateGateway:
    """Implement the queue/progress port without importing RQ during API startup."""

    def __init__(self, client, host: str):
        self.client = client
        self.host = host

    def enqueue(self, puuid: str, count: int) -> None:
        """Load the platform-specific RQ adapter only for an actual enqueue."""
        from .rq_queue import enqueue_update  # pylint: disable=import-outside-toplevel
        enqueue_update(self.host, puuid, count)

    async def progress(self, puuid: str) -> tuple[int, int]:
        """Read the existing Redis tracking keys."""
        key = f'nexus_iq:summoner_updates:{puuid}'
        return int(await self.client.scard(key)), int(await self.client.get(f'{key}:total_jobs') or 0)

    async def subscribe(self, puuid: str):
        """Yield raw updates and keepalive markers, cleaning up on cancellation."""
        channel = f'nexus_iq:summoner_profile:{puuid}'
        pubsub = self.client.pubsub(ignore_subscribe_messages=True)
        try:
            await pubsub.subscribe(channel)
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is None:
                    yield None
                elif message['type'] == 'message':
                    yield message['data']
                await asyncio.sleep(0.1)
        finally:
            with CancelScope(shield=True):
                with suppress(Exception):
                    await pubsub.unsubscribe(channel)
                await pubsub.aclose()
