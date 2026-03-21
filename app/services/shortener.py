from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.url import URL
from app.schemas.url import ShortenResponse
from app.utils import base62

_TMP_PREFIX = "tmp"


async def short_code_exists(session: AsyncSession, code: str) -> bool:
    r = await session.execute(select(URL.id).where(URL.short_code == code).limit(1))
    return r.scalar_one_or_none() is not None


def _public_origin() -> str:
    return str(get_settings().public_base_url).rstrip("/")


def _build_short_url(code: str) -> str:
    return urljoin(_public_origin() + "/", code)


async def shorten_url(
    session: AsyncSession,
    *,
    original_url: str,
    custom_alias: str | None,
    ttl_hours: int | None,
) -> ShortenResponse:
    now = datetime.now(timezone.utc)
    expires_at: datetime | None = None
    if ttl_hours is not None:
        expires_at = now + timedelta(hours=ttl_hours)

    if custom_alias:
        if await short_code_exists(session, custom_alias):
            raise ValueError("alias_taken")
        row = URL(
            short_code=custom_alias,
            original_url=original_url,
            custom_alias=custom_alias,
            expires_at=expires_at,
        )
        session.add(row)
        await session.flush()
    else:
        pending = f"{_TMP_PREFIX}{uuid.uuid4().hex}"
        row = URL(
            short_code=pending,
            original_url=original_url,
            custom_alias=None,
            expires_at=expires_at,
        )
        session.add(row)
        await session.flush()
        row.short_code = base62.encode(row.id)
        await session.flush()

    return ShortenResponse(
        short_url=_build_short_url(row.short_code),
        code=row.short_code,
        expires_at=row.expires_at,
    )
