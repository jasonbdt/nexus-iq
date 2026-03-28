from typing import Annotated

import os
import asyncio

from fastapi import Depends

import redis.asyncio as redis

_STATE: redis.Redis | None = None



async def init_redis() -> redis.Redis:
    global _STATE
    _STATE = redis.Redis(host=os.getenv("REDIS_HOST"))
    return _STATE


def get_redis() -> redis.Redis:
    if _STATE is None:
        raise RuntimeError("Redis not initialized. FastAPI lifespan didn't run?")
    return _STATE


async def close_redis() -> None:
    global _STATE
    if _STATE is not None:
        await _STATE.aclose()
    _STATE = None

RedisDep = Annotated[redis.Redis, Depends(get_redis)]


