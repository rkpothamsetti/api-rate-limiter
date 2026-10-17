import pytest

from app.services.limiter import RateLimiter


@pytest.mark.asyncio
async def test_sliding_window_limit(redis_client):
    limiter = RateLimiter(redis_client)

    first = await limiter.check(1001, 2, 60)
    second = await limiter.check(1001, 2, 60)
    third = await limiter.check(1001, 2, 60)

    assert first["allowed"] is True
    assert second["allowed"] is True
    assert third["allowed"] is False
    assert third["retry_after"] > 0