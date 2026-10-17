from datetime import datetime, timezone

from redis.exceptions import RedisError
from sqlalchemy.exc import OperationalError

from app.api.routes import demo
from app.db.models import APIClient, RequestLog
from app.db.session import get_db


def test_valid_invalid_and_inactive_api_keys(
    api_client, test_db, registered_client, monkeypatch
):
    class AllowLimiter:
        def __init__(self, redis):
            pass

        async def check(self, client_id, limit, window_seconds):
            return {
                "allowed": True,
                "remaining": limit - 1,
                "retry_after": 0,
                "limit": limit,
            }

    monkeypatch.setattr(demo, "RateLimiter", AllowLimiter)

    valid_response = api_client.get(
        "/protected",
        headers={"X-API-Key": registered_client["api_key"]},
    )
    invalid_response = api_client.get(
        "/protected",
        headers={"X-API-Key": "not-a-valid-key"},
    )

    db = test_db()
    client = db.get(APIClient, registered_client["id"])
    client.is_active = False
    db.commit()
    db.close()

    inactive_response = api_client.get(
        "/protected",
        headers={"X-API-Key": registered_client["api_key"]},
    )

    assert valid_response.status_code == 200
    assert valid_response.json()["message"] == "Request allowed"
    assert invalid_response.status_code == 401
    assert inactive_response.status_code == 401


def test_rate_limit_returns_429_and_headers(
    api_client, registered_client, monkeypatch
):
    class DenyLimiter:
        def __init__(self, redis):
            pass

        async def check(self, client_id, limit, window_seconds):
            return {
                "allowed": False,
                "remaining": 0,
                "retry_after": 17,
                "limit": limit,
            }

    monkeypatch.setattr(demo, "RateLimiter", DenyLimiter)
    response = api_client.get(
        "/protected",
        headers={"X-API-Key": registered_client["api_key"]},
    )

    assert response.status_code == 429
    assert response.json() == {"detail": "Rate limit exceeded"}
    assert response.headers["Retry-After"] == "17"
    assert response.headers["X-RateLimit-Limit"] == "2"
    assert response.headers["X-RateLimit-Remaining"] == "0"


def test_analytics_reports_totals_and_rejections(
    api_client, test_db, registered_client
):
    db = test_db()
    db.add_all(
        [
            RequestLog(
                client_id=registered_client["id"],
                endpoint="/protected",
                status_code=status_code,
                latency_ms=10,
                created_at=datetime.now(timezone.utc),
            )
            for status_code in (200, 429, 429)
        ]
    )
    db.commit()
    db.close()

    response = api_client.get(
        "/analytics/summary",
        headers={"X-API-Key": registered_client["api_key"]},
    )

    assert response.status_code == 200
    assert response.json()["total_requests"] == 3
    assert response.json()["rejected_requests"] == 2
    assert response.json()["allowed_requests"] == 1


def test_database_failure_returns_server_error(
    api_client, registered_client
):
    def failing_db():
        class BrokenSession:
            def scalar(self, statement):
                raise OperationalError(
                    "SELECT api_clients",
                    {},
                    RuntimeError("database unavailable"),
                )

        yield BrokenSession()

    api_client.app.dependency_overrides[get_db] = failing_db
    try:
        response = api_client.get(
            "/protected",
            headers={"X-API-Key": registered_client["api_key"]},
        )
    finally:
        api_client.app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500


def test_redis_failure_returns_server_error(
    api_client, registered_client, monkeypatch
):
    class FailingLimiter:
        def __init__(self, redis):
            pass

        async def check(self, client_id, limit, window_seconds):
            raise RedisError("Redis unavailable")

    monkeypatch.setattr(demo, "RateLimiter", FailingLimiter)
    response = api_client.get(
        "/protected",
        headers={"X-API-Key": registered_client["api_key"]},
    )

    assert response.status_code == 500
