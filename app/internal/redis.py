"""
Redis helpers for shared state, dependency access, and Riot Games API
rate limiting.

This module provides Redis initialization and access helpers used by the
application runtime, along with a token-bucket-based rate limiting
mechanism for Riot API requests. It centralizes Redis state management,
FastAPI dependency wiring, and request throttling logic backed by a
Lua script to keep bucket updates atomic.

The rate limiter operates per Riot routing value and is designed to
enforce regional request limits consistently across concurrent workers
and requests.
"""
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
    """
    Builds the Redis key for the token bucket of a Riot routing value.

    Args:
        routing: The Riot routing value used to scope the token bucket.

    Returns:
        str: The Redis key for the routing-specific token bucket.
    """
    return f"bucket:riot:{routing}"


async def init_redis() -> redis.Redis:
    """
    Initializes and stores the shared Redis client for the application.

    This function creates the Redis client instance used by the
    application lifecycle and stores it in module-level state so it
    can be reused by dependencies and helper functions.

    Returns:
        redis.Redis: The initialized Redis client instance.
    """
    global _STATE
    _STATE = redis.Redis(host=os.getenv("REDIS_HOST"))
    return _STATE


def get_redis() -> redis.Redis:
    """
    Returns the initialized shared Redis client.

    Raises:
        RuntimeError: If Redis has not been initialized yet.

    Returns:
        redis.Redis: The shared Redis client instance.
    """
    if _STATE is None:
        raise RuntimeError("Redis not initialized. FastAPI lifespan didn't run?")
    return _STATE


async def close_redis() -> None:
    """
    Closes the shared Redis client and clears the stored module state.

    This function should be called during application shutdown to ensure
    the Redis connection is closed cleanly and the cached
    client reference is removed.

    Returns:
        None
    """
    global _STATE
    if _STATE is not None:
        await _STATE.aclose()
    _STATE = None

RedisDep = Annotated[redis.Redis, Depends(get_redis)]

def _redis_client() -> redis.Redis:
    """
    Returns a Redis client for internal helper usage.

    The function prefers the initialized shared Redis client.

    If Redis has not been initialized through the application lifecycle,
    it falls back to creating a direct client instance.

    Returns:
        redis.Redis: A usable Redis client instance.
    """
    try:
        return get_redis()
    except RuntimeError:
        return redis.Redis(host=os.getenv("REDIS_HOST"))


async def try_acquire(
    routing: str,
    max_tokens: float = 5.0,
    refill_per_second: float = 0.85,
) -> tuple[bool, float, int | None]:
    """
    Attempts to acquire a token from the routing-specific token bucket.

    This function executes the Redis Lua script atomically to refill
    the bucket based on elapsed time, consume one token if available,
    and return the current acquisition result.

    Args:
        routing: The Riot routing value whose bucket should be checked.
        max_tokens: The maximum number of tokens the bucket can hold.
        refill_per_second: The token refill rate per second.

    Returns:
        tuple[bool, float, int | None]: A tuple containing whether
        acquisition was allowed, the remaining token count, and an
        optional retry delay in seconds if the request was rejected.
    """
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
    """
    Waits until a token can be acquired from the routing-specific bucket.

    This helper repeatedly attempts token acquisition until it succeeds or the
    configured maximum wait time is exceeded. Between attempts, it sleeps for a
    short bounded interval derived from the suggested retry delay.

    Args:
        routing: The Riot routing value whose bucket should be used.
        max_tokens: The maximum number of tokens the bucket can hold.
        refill_per_second: The token refill rate per second.
        max_wait: The maximum number of seconds to wait for acquisition.

    Raises:
        TimeoutError: If no token could be acquired within the configured wait
            time.

    Returns:
        None
    """
    deadline = time.monotonic() + max_wait

    while time.monotonic() < deadline:
        allowed, remaining, retry_after = await try_acquire(
            routing, max_tokens, refill_per_second
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
    Waits for permission to perform a Riot API request for the given
    routing.

    This helper applies the default Riot routing bucket settings and
    blocks until a token becomes available or the maximum wait time is
    exceeded.

    Args:
        routing: The Riot routing value whose rate limit bucket
                 should be used.
        max_wait: The maximum number of seconds to wait for an
                  available token.

    Raises:
        TimeoutError: If no token could be acquired within the
                      configured wait time.

    Returns:
        None
    """
    await wait_acquire(
        routing,
        max_tokens=RIOT_ROUTING_MAX_TOKENS,
        refill_per_second=RIOT_ROUTING_REFILL_PER_SECOND,
        max_wait=max_wait
    )
