from typing import Annotated

import os
import asyncio

from fastapi import Depends
from redis import Redis

_lock = asyncio.Lock()
_STATE: Redis | None = None


async def init_redis() -> Redis:
    async with _lock:
        global _STATE
        _STATE = Redis(host=os.getenv("REDIS_HOST"), decode_responses=True)
        return _STATE


def get_redis() -> Redis:
    if _STATE is None:
        raise RuntimeError("Redis not initialized. FastAPI lifespan didn't run?")
    return _STATE


async def close_redis() -> None:
    async with _lock:
        global _STATE
        if _STATE is not None:
            _STATE.close()
        _STATE = None

RedisDep = Annotated[Redis, Depends(get_redis)]
