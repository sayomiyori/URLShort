from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.click import Click
from app.models.url import URL


@pytest.mark.asyncio
async def test_shorten_returns_code_and_short_url(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com/path"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["code"]
    assert data["short_url"].endswith("/" + data["code"])
    assert data["expires_at"] is None


@pytest.mark.asyncio
async def test_shorten_with_ttl(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com/", "ttl_hours": 24},
    )
    assert r.status_code == 200
    assert r.json()["expires_at"] is not None


@pytest.mark.asyncio
async def test_shorten_custom_alias(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/shorten",
        json={"url": "https://example.org/", "custom_alias": "my-link-1"},
    )
    assert r.status_code == 200
    assert r.json()["code"] == "my-link-1"


@pytest.mark.asyncio
async def test_shorten_custom_alias_conflict(client: AsyncClient) -> None:
    body = {"url": "https://a.com/", "custom_alias": "dup"}
    assert (await client.post("/api/v1/shorten", json=body)).status_code == 200
    r2 = await client.post(
        "/api/v1/shorten",
        json={"url": "https://b.com/", "custom_alias": "dup"},
    )
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_shorten_invalid_alias(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com/", "custom_alias": "ab"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_redirect_301(client: AsyncClient) -> None:
    cr = await client.post(
        "/api/v1/shorten",
        json={"url": "https://target.example/landing"},
    )
    code = cr.json()["code"]
    r = await client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://target.example/landing"


@pytest.mark.asyncio
async def test_redirect_records_click_in_background(client: AsyncClient) -> None:
    from app.db.session import AsyncSessionLocal

    cr = await client.post(
        "/api/v1/shorten",
        json={"url": "https://click.test/page"},
    )
    code = cr.json()["code"]
    await client.get(
        f"/{code}",
        follow_redirects=False,
        headers={"User-Agent": "pytest-httpx/1.0", "Referer": "https://from.test/"},
    )
    await asyncio.sleep(0.2)

    async with AsyncSessionLocal() as s:
        q = await s.execute(select(URL).where(URL.short_code == code))
        url_row = q.scalar_one()
        n = await s.execute(select(func.count()).select_from(Click).where(Click.url_id == url_row.id))
        assert int(n.scalar_one()) == 1
        assert url_row.click_count == 1


@pytest.mark.asyncio
async def test_stats(client: AsyncClient) -> None:
    cr = await client.post(
        "/api/v1/shorten",
        json={"url": "https://stats.test/"},
    )
    code = cr.json()["code"]
    for _ in range(3):
        await client.get(f"/{code}", follow_redirects=False)
    await asyncio.sleep(0.25)

    sr = await client.get(f"/api/v1/stats/{code}")
    assert sr.status_code == 200
    body = sr.json()
    assert body["total_clicks"] == 3
    assert body["original_url"] == "https://stats.test/"
    assert isinstance(body["clicks_by_day"], list)
    assert isinstance(body["top_referers"], list)
    assert isinstance(body["top_devices"], list)


@pytest.mark.asyncio
async def test_stats_not_found(client: AsyncClient) -> None:
    r = await client.get("/api/v1/stats/does-not-exist-xyz")
    assert r.status_code == 404
