import asyncio
from uuid import uuid4

import pytest

from app.services.limiter import RateLimiter


@pytest.mark.asyncio
async def test_sliding_window_limit(redis_client):
    limiter = RateLimiter(redis_client)
    client_id = uuid4().int

    try:
        first = await limiter.check(client_id, 2, 60)
        second = await limiter.check(client_id, 2, 60)
        third = await limiter.check(client_id, 2, 60)

        assert first["allowed"] is True
        assert second["allowed"] is True
        assert third["allowed"] is False
        assert third["retry_after"] > 0
    finally:
        await redis_client.delete(f"rate-limit:{client_id}")


@pytest.mark.asyncio
async def test_sliding_window_allows_requests_after_window(redis_client):
    limiter = RateLimiter(redis_client)
    client_id = uuid4().int
    key = f"rate-limit:{client_id}"

    try:
        first = await limiter.check(client_id, 1, 1)
        blocked = await limiter.check(client_id, 1, 1)
        await asyncio.sleep(1.1)
        after_window = await limiter.check(client_id, 1, 1)

        assert first["allowed"] is True
        assert blocked["allowed"] is False
        assert after_window["allowed"] is True
    finally:
        await redis_client.delete(key)


@pytest.mark.asyncio
async def test_concurrent_requests_do_not_exceed_limit(redis_client):
    limiter = RateLimiter(redis_client)
    client_id = uuid4().int
    key = f"rate-limit:{client_id}"

    try:
        results = await asyncio.gather(
            *(limiter.check(client_id, 5, 60) for _ in range(20))
        )

        assert sum(result["allowed"] for result in results) == 5
        assert all(result["remaining"] >= 0 for result in results)
    finally:
        await redis_client.delete(key)