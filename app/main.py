import asyncio
import logging
from contextlib import asynccontextmanager, suppress

import redis.asyncio as redis
from fastapi import FastAPI
from sqlalchemy import func, select
from starlette.requests import Request
from starlette_prometheus import PrometheusMiddleware, metrics as starlette_metrics

from app import metrics as prom_metrics
from app.api.v1.redirect import router as redirect_router
from app.api.v1.router import api_router
from app.cache import click_counter
from app.config import get_settings
from app.db.session import AsyncSessionLocal
from app.middleware.rate_limit import RateLimitMiddleware
from app.models.url import URL

log = logging.getLogger(__name__)


async def _refresh_active_urls_gauge() -> None:
    try:
        async with AsyncSessionLocal() as session:
            r = await session.execute(
                select(func.count()).select_from(URL).where(URL.is_active.is_(True))
            )
            prom_metrics.active_urls_total.set(int(r.scalar_one() or 0))
    except Exception:
        log.exception("active_urls_total refresh failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    r: redis.Redis | None = None
    try:
        r = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
        )
        await r.ping()
        app.state.redis = r
    except Exception as exc:  # pragma: no cover
        log.warning("Redis unavailable, running without cache/rate limits: %s", exc)
        app.state.redis = None
        r = None

    async def flush_loop() -> None:
        try:
            while True:
                await asyncio.sleep(60.0)
                if app.state.redis is not None:
                    try:
                        await click_counter.flush_to_postgres(
                            app.state.redis,
                            AsyncSessionLocal,
                        )
                    except Exception:
                        log.exception("scheduled click counter flush failed")
        except asyncio.CancelledError:
            raise

    async def gauge_loop() -> None:
        try:
            while True:
                await asyncio.sleep(10.0)
                prom_metrics.refresh_cache_hit_ratio_gauge()
                await _refresh_active_urls_gauge()
        except asyncio.CancelledError:
            raise

    flush_task = asyncio.create_task(flush_loop()) if r is not None else None
    gauge_task = asyncio.create_task(gauge_loop())
    try:
        yield
    finally:
        for task in (flush_task, gauge_task):
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        if r is not None:
            with suppress(Exception):
                await click_counter.flush_to_postgres(r, AsyncSessionLocal)
            with suppress(Exception):
                await r.aclose()
        app.state.redis = None


app = FastAPI(title="URLShort", lifespan=lifespan)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(PrometheusMiddleware, filter_unhandled_paths=True)


@app.get("/metrics", include_in_schema=False)
async def metrics_endpoint(request: Request):
    return starlette_metrics(request)


app.include_router(api_router, prefix="/api/v1")
app.include_router(redirect_router)
