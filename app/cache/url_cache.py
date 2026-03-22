"""Redis cache for URL redirect lookups (cache-aside)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis

URL_KEY_PREFIX = "url:"
URL_CACHE_TTL_SECONDS = 3600


@dataclass(frozen=True)
class CachedUrl:
    original_url: str
    is_active: bool
    expires_at: datetime | None
    url_id: int

    def is_valid_now(self) -> bool:
        if not self.is_active:
            return False
        if self.expires_at is None:
            return True
        return self.expires_at >= datetime.now(timezone.utc)


def _key(short_code: str) -> str:
    return f"{URL_KEY_PREFIX}{short_code}"


def _serialize(
    *,
    original_url: str,
    is_active: bool,
    expires_at: datetime | None,
    url_id: int,
) -> str:
    payload = {
        "original_url": original_url,
        "is_active": is_active,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "url_id": url_id,
    }
    return json.dumps(payload, separators=(",", ":"))


def _deserialize(raw: str) -> CachedUrl | None:
    try:
        d = json.loads(raw)
        exp = d.get("expires_at")
        # Python 3.11+ fromisoformat handles 'Z' suffix natively
        expires_at = datetime.fromisoformat(exp) if exp else None
        return CachedUrl(
            original_url=d["original_url"],
            is_active=bool(d["is_active"]),
            expires_at=expires_at,
            url_id=int(d["url_id"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


async def get_cached(redis: Redis | None, short_code: str) -> CachedUrl | None:
    if redis is None:
        return None
    # Redis client is configured with decode_responses=True, so raw is always str
    raw: str | None = await redis.get(_key(short_code))
    if raw is None:
        return None
    return _deserialize(raw)


async def set_cached(
    redis: Redis | None,
    short_code: str,
    *,
    original_url: str,
    is_active: bool,
    expires_at: datetime | None,
    url_id: int,
) -> None:
    if redis is None:
        return
    await redis.set(
        _key(short_code),
        _serialize(
            original_url=original_url,
            is_active=is_active,
            expires_at=expires_at,
            url_id=url_id,
        ),
        ex=URL_CACHE_TTL_SECONDS,
    )


async def invalidate(redis: Redis | None, short_code: str) -> None:
    if redis is None:
        return
    await redis.delete(_key(short_code))
