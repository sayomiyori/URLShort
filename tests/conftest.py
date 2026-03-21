from __future__ import annotations

import asyncio
import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://urlshort:urlshort@127.0.0.1:5432/urlshort",
    )
os.environ.setdefault("PUBLIC_BASE_URL", "http://testserver")

from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture(scope="function")
async def db_schema() -> None:
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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


