"""Redis rate limiting with explicit client ownership."""
import asyncio
import time

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


class RiotRateLimiter:
    """Preserve atomic per-routing Redis token buckets across workers."""

    def __init__(self, client):
        self.client = client

    async def acquire(self, routing: str, max_wait: float = 180.0) -> None:
        """Wait for the existing 20-token, 100/120-second routing budget."""
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            result = await self.client.eval(
                LUA_SCRIPT, 1, f'bucket:riot:{routing}', '20.0', str(100.0 / 120.0),
            )
            if int(result[0]) == 1:
                return
            await asyncio.sleep(1.0)
        raise TimeoutError(f'Token bucket exceeded {max_wait}s for routing={routing}')
