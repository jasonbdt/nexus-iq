from typing import Annotated, Optional

import os
import math
import time
import asyncio

from fastapi import Depends

import redis.asyncio as redis

_STATE: redis.Redis | None = None

LUA_SCRIPT = """
local key = KEYS[1]
local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])

local t = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000

local data = redis.call('HGETALL', key)
local tokens = max_tokens
local last_refill = now

if #data > 0 then
  local fields = {}
  for i = 1, #data, 2 do
    fields[data[i]] = data[i + 1]
  end

  tokens = tonumber(fields['tokens']) or max_tokens
  last_refill = tonumber(fields['last_refill']) or now
end

-- Refill tokens based on elapsed time
local elapsed = now - last_refill
local new_tokens = elapsed * refill_rate
tokens = math.min(max_tokens, tokens + new_tokens)

local allowed = 0
local remaining = tokens

if tokens >= 1 then
  tokens = tokens - 1
  remaining = tokens
  allowed = 1
end

redis.call('HSET', key, 'tokens', tostring(tokens), 'last_refill', tostring(now))
redis.call('EXPIRE', key, math.ceil(max_tokens / refill_rate) + 1)

return { allowed, math.floor(remaining) }
"""

def bucket_key(routing: str) -> str:
    return f"bucket:riot:{routing}"


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

def _redis_client() -> redis.Redis:
    try:
        return get_redis()
    except RuntimeError:
        return redis.Redis(host=os.getenv("REDIS_HOST"))


async def try_acquire(
    routing: str,
    max_tokens: float = 5.0,
    refill_per_second: float = 0.85,
) -> tuple[bool, float, int | None]:
    redis_conn = _redis_client()

    key = bucket_key(routing)
    result = await redis_conn.eval(
        LUA_SCRIPT, 1, key,
        str(max_tokens), str(refill_per_second)
    )

    allowed = int(result[0]) == 1
    remaining = float(result[1])
    retry_after: Optional[int] = None
    if not allowed:
        retry_after = int(math.floor(1 / refill_per_second))

    return allowed, remaining, retry_after


async def wait_acquire(
    routing: str,
    max_tokens: float = 5.0,
    refill_per_second: float = 0.85,
    max_wait: float = 180.0
) -> None:
    deadline = time.monotonic() + max_wait

    while time.monotonic() < deadline:
        allowed, remaining, retry_after = await try_acquire(
            redis, routing, max_tokens, refill_per_second
        )

        if allowed:
            return
        wait_sec = max(0.1, min(1.0, retry_after or 1.0))
        await asyncio.sleep(wait_sec)
    raise TimeoutError(f"Token bucket exceeded {max_wait}s for routing={routing}")


# Per-region bucket: Riot dev key = 100 req/120s + 20 req/s burst (limits apply per region)
RIOT_ROUTING_MAX_TOKENS = 20.0
RIOT_ROUTING_REFILL_PER_SECOND = 100.0 / 120.0  # ~0.833


async def acquire_riot(
    routing: str,
    max_wait: float = 180.0,
) -> None:
    """
    Acquire from per-region token bucket before a Riot API request.

    Riot limits (per region): 100 req/120s, 20 req/s burst.
    Single bucket with max_tokens=20 and refill=100/120 enforces both.
    """
    await wait_acquire(
        routing,
        max_tokens=RIOT_ROUTING_MAX_TOKENS,
        refill_per_second=RIOT_ROUTING_REFILL_PER_SECOND,
        max_wait=max_wait
    )
