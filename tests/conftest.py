from __future__ import annotations

import os

import pytest
import redis.asyncio as redis_lib
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://urlshort:urlshort@127.0.0.1:5433/urlshort",
    )
os.environ.setdefault("PUBLIC_BASE_URL", "http://testserver")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6380/15")

from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture(scope="function")
async def db_schema() -> None:
    rurl = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/15")
    rc = redis_lib.from_url(rurl, decode_responses=True)
    try:
        await rc.ping()
        await rc.flushdb()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Redis unavailable: {exc}")
    await rc.aclose()

    # Dispose the pool so connections from previous event loop are dropped.
    await engine.dispose()

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"PostgreSQL unavailable: {exc}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture
async def client(db_schema: None) -> AsyncClient:
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


@pytest.fixture
def low_rate_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_REDIRECT_PER_MINUTE", "5")
    monkeypatch.setenv("RATE_LIMIT_SHORTEN_PER_MINUTE", "3")
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
