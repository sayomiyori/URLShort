import asyncio
import logging
from contextlib import asynccontextmanager, suppress

import redis.asyncio as redis
from fastapi import FastAPI
from prometheus_client import make_asgi_app

from app.api.v1.redirect import router as redirect_router
from app.api.v1.router import api_router
from app.cache import click_counter
from app.config import get_settings
from app.db.session import AsyncSessionLocal
from app.middleware.rate_limit import RateLimitMiddleware

log = logging.getLogger(__name__)


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

    task = asyncio.create_task(flush_loop()) if r is not None else None
    try:
        yield
    finally:
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

app.mount("/metrics", make_asgi_app())
app.add_middleware(RateLimitMiddleware)

app.include_router(api_router, prefix="/api/v1")
app.include_router(redirect_router)
