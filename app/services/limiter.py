import math
import time
import uuid

from redis.asyncio import Redis


SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

local cutoff = now - window

redis.call("ZREMRANGEBYSCORE", key, "-inf", cutoff)

local count = redis.call("ZCARD", key)

if count >= limit then
    local oldest = redis.call("ZRANGE", key, 0, 0, "WITHSCORES")
    local retry = 1

    if #oldest > 0 then
        retry = math.max(
            1,
            math.ceil(tonumber(oldest[2]) + window - now)
        )
    end

    redis.call("EXPIRE", key, window + 1)
    return {0, 0, retry}
end

redis.call("ZADD", key, now, member)

local remaining = limit - count - 1

redis.call("EXPIRE", key, window + 1)

return {1, remaining, 0}
"""


class RateLimiter:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def check(
        self,
        client_id: int,
        limit: int,
        window_seconds: int,
    ):
        now = time.time()
        key = f"rate-limit:{client_id}"
        member = f"{now}:{uuid.uuid4().hex}"

        result = await self.redis.eval(
            SLIDING_WINDOW_SCRIPT,
            1,
            key,
            now,
            window_seconds,
            limit,
            member,
        )

        return {
            "allowed": bool(result[0]),
            "remaining": int(result[1]),
            "retry_after": int(result[2]),
            "limit": limit,
        }