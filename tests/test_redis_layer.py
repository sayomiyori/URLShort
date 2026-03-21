from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from prometheus_client import REGISTRY
from sqlalchemy import select

from app.cache import click_counter, url_cache
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.url import URL


def _counter_value(metric_base_name: str) -> float:
    for metric in REGISTRY.collect():
        if metric.name != metric_base_name:
            continue
        for s in metric.samples:
            if s.name == f"{metric_base_name}_total":
                return float(s.value)
    return 0.0


@pytest.mark.asyncio
async def test_url_cache_miss_then_hit(client: AsyncClient) -> None:
    hits0 = _counter_value("urlshort_url_cache_hit")
    miss0 = _counter_value("urlshort_url_cache_miss")

    cr = await client.post(
        "/api/v1/shorten",
        json={"url": "https://cache.test/page"},
    )
    assert cr.status_code == 200
    code = cr.json()["code"]

    r1 = await client.get(f"/{code}", follow_redirects=False)
    assert r1.status_code == 301
    miss1 = _counter_value("urlshort_url_cache_miss")
    assert miss1 == miss0 + 1

    r2 = await client.get(f"/{code}", follow_redirects=False)
    assert r2.status_code == 301
    hits2 = _counter_value("urlshort_url_cache_hit")
    assert hits2 == hits0 + 1


@pytest.mark.asyncio
async def test_shorten_invalidates_url_cache(client: AsyncClient) -> None:
    cr = await client.post(
        "/api/v1/shorten",
        json={"url": "https://inv.test/"},
    )
    code = cr.json()["code"]
    await client.get(f"/{code}", follow_redirects=False)

    rredis = app.state.redis
    assert rredis is not None
    assert await rredis.get(f"url:{code}") is not None

    await url_cache.invalidate(rredis, code)
    assert await rredis.get(f"url:{code}") is None


@pytest.mark.asyncio
async def test_rate_limit_redirect_429(client: AsyncClient, low_rate_limits: None) -> None:
    cr = await client.post(
        "/api/v1/shorten",
        json={"url": "https://rl.test/"},
    )
    code = cr.json()["code"]

    last = None
    for _ in range(6):
        last = await client.get(f"/{code}", follow_redirects=False)
    assert last is not None
    assert last.status_code == 429
    assert "retry-after" in {k.lower() for k in last.headers}
    ra = last.headers.get("Retry-After") or last.headers.get("retry-after")
    assert ra is not None
    assert int(ra) >= 1


@pytest.mark.asyncio
async def test_rate_limit_shorten_429(client: AsyncClient, low_rate_limits: None) -> None:
    last = None
    for i in range(4):
        last = await client.post(
            "/api/v1/shorten",
            json={"url": f"https://s{i}.test/"},
            headers={"X-API-Key": "same-key"},
        )
    assert last is not None
    assert last.status_code == 429
    assert last.headers.get("Retry-After") or last.headers.get("retry-after")


@pytest.mark.asyncio
async def test_click_counter_flush_to_postgres(client: AsyncClient) -> None:
    cr = await client.post(
        "/api/v1/shorten",
        json={"url": "https://flush.test/"},
    )
    code = cr.json()["code"]

    for _ in range(3):
        await client.get(f"/{code}", follow_redirects=False)
    await asyncio.sleep(0.15)

    rredis = app.state.redis
    assert rredis is not None
    raw = await rredis.get(f"clicks:{code}")
    assert raw is not None
    assert int(raw) == 3

    n = await click_counter.flush_to_postgres(rredis, AsyncSessionLocal)
    assert n >= 1
    assert await rredis.get(f"clicks:{code}") is None

    async with AsyncSessionLocal() as s:
        row = (
            await s.execute(select(URL).where(URL.short_code == code))
        ).scalar_one()
        assert row.click_count == 3
