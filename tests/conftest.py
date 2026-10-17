from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.security import hash_api_key
from app.db.models import APIClient, RateLimitPolicy
from app.db.session import Base, get_db
from app.main import app


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator[Redis]:
    client = Redis.from_url(
        get_settings().redis_url,
        decode_responses=True,
    )
    try:
        await client.ping()
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    def override_get_db():
        db = test_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield test_session_local
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def api_client(test_db):
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def registered_client(test_db):
    api_key = "test-api-key"
    db = test_db()
    client = APIClient(
        name="Test client",
        key_hash=hash_api_key(api_key),
    )
    client.policies.append(
        RateLimitPolicy(
            endpoint="*",
            limit_count=2,
            window_seconds=60,
        )
    )
    db.add(client)
    db.commit()
    result = {"id": client.id, "api_key": api_key}
    db.close()
    return result
