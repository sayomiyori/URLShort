"""Redis INCR for redirect clicks; periodic flush to PostgreSQL."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import update

from app.models.url import URL

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

log = logging.getLogger(__name__)

CLICK_KEY_PREFIX = "clicks:"

_LUA_TAKE_AND_DEL = """
local v = redis.call('GET', KEYS[1])
if not v then return 0 end
local n = tonumber(v)
if n == nil or n <= 0 then return 0 end
redis.call('DEL', KEYS[1])
return n
"""


def _click_key(short_code: str) -> str:
    return f"{CLICK_KEY_PREFIX}{short_code}"


async def increment(redis: Redis | None, short_code: str) -> None:
    if redis is None:
        return
    await redis.incr(_click_key(short_code))


async def increment_pg_when_no_redis(url_id: int) -> None:
    """Fallback when Redis is down: bump url.click_count in PostgreSQL."""
    from sqlalchemy import update

    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        try:
            t = URL.__table__
            await session.execute(
                update(t)
                .where(t.c.id == url_id)
                .values(click_count=t.c.click_count + 1)
            )
            await session.commit()
        except Exception:
            await session.rollback()
            log.exception("pg click_count fallback failed for url_id=%s", url_id)


async def flush_to_postgres(
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Drain Redis click counters into url.click_count. Returns keys successfully applied."""
    flushed = 0
    async for keyb in redis.scan_iter(f"{CLICK_KEY_PREFIX}*", count=100):
        key = keyb.decode() if isinstance(keyb, bytes) else keyb
        if not key.startswith(CLICK_KEY_PREFIX):
            continue
        short_code = key[len(CLICK_KEY_PREFIX) :]
        if not short_code:
            continue
        n = await redis.eval(_LUA_TAKE_AND_DEL, 1, key)
        n = int(n)
        if n <= 0:
            continue
        try:
            async with session_factory() as session:
                try:
                    t = URL.__table__
                    await session.execute(
                        update(t)
                        .where(t.c.short_code == short_code)
                        .values(click_count=t.c.click_count + n)
                    )
                    await session.commit()
                    flushed += 1
                except Exception:
                    await session.rollback()
                    await redis.incrby(key, n)
                    log.exception("flush click counter failed for %s", short_code)
        except Exception:
            await redis.incrby(key, n)
            log.exception("flush click counter session error for %s", short_code)
    return flushed
