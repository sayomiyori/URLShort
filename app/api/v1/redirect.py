from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import click_counter, url_cache
from app.db.session import AsyncSessionLocal, get_db
from app.services import analytics

router = APIRouter()

_RESERVED = frozenset({"api", "metrics"})


async def _record_click_background(
    url_id: int,
    ip_address: str,
    user_agent: str,
    referer: str | None,
) -> None:
    async with AsyncSessionLocal() as session:
        try:
            await analytics.record_click(
                session,
                url_id=url_id,
                ip_address=ip_address,
                user_agent=user_agent,
                referer=referer,
            )
            await session.commit()
        except Exception:
            await session.rollback()


@router.get("/{code}")
async def redirect_by_code(
    code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    if code in _RESERVED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")

    rredis = getattr(request.app.state, "redis", None)

    cached = await url_cache.get_cached(rredis, code)
    if cached is not None and not cached.is_valid_now():
        await url_cache.invalidate(rredis, code)
        cached = None

    if cached is not None and cached.is_valid_now():
        url_cache.CACHE_HIT.inc()
        original_url = cached.original_url
        url_id = cached.url_id
    else:
        url_cache.CACHE_MISS.inc()
        row = await analytics.get_active_url_by_code(db, code)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
        await url_cache.set_cached(
            rredis,
            code,
            original_url=row.original_url,
            is_active=row.is_active,
            expires_at=row.expires_at,
            url_id=row.id,
        )
        original_url = row.original_url
        url_id = row.id

    if rredis is not None:
        await click_counter.increment(rredis, code)
    else:
        background_tasks.add_task(click_counter.increment_pg_when_no_redis, url_id)

    client = request.client
    ip = client.host if client else "0.0.0.0"
    ua = request.headers.get("user-agent") or ""
    ref = request.headers.get("referer")

    background_tasks.add_task(
        _record_click_background,
        url_id,
        ip,
        ua,
        ref,
    )

    return RedirectResponse(url=original_url, status_code=301)
