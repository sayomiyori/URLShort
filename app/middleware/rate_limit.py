"""Sliding-window rate limits in Redis (ZSET)."""

from __future__ import annotations

import math
import time
import uuid
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app import metrics as prom_metrics
from app.config import get_settings

if TYPE_CHECKING:
    from redis.asyncio import Redis


def _client_ip(request: Request) -> str:
    if request.client:
        return request.client.host
    return "0.0.0.0"


def _is_redirect_get(request: Request) -> bool:
    if request.method != "GET":
        return False
    path = request.url.path
    if path.startswith("/api") or path.startswith("/metrics"):
        return False
    if path in ("/docs", "/redoc", "/openapi.json", "/favicon.ico"):
        return False
    segments = [p for p in path.split("/") if p]
    return len(segments) == 1


def _is_shorten_post(request: Request) -> bool:
    return request.method == "POST" and request.url.path.rstrip("/") == "/api/v1/shorten"


def _api_key_identity(request: Request) -> str:
    key = request.headers.get("x-api-key") or request.headers.get("X-API-Key")
    if key:
        return f"key:{key}"
    return f"anon:{_client_ip(request)}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        redis: Redis | None = getattr(request.app.state, "redis", None)
        if redis is None:
            return await call_next(request)

        settings = get_settings()
        now = time.time()
        window = 60.0

        if _is_redirect_get(request):
            limit = settings.rate_limit_redirect_per_minute
            bucket = f"rl:redirect:{_client_ip(request)}"
        elif _is_shorten_post(request):
            limit = settings.rate_limit_shorten_per_minute
            bucket = f"rl:shorten:{_api_key_identity(request)}"
        else:
            return await call_next(request)

        member = f"{now}:{uuid.uuid4().hex}"
        pipe = redis.pipeline(transaction=True)
        pipe.zremrangebyscore(bucket, 0, now - window)
        pipe.zcard(bucket)
        results = await pipe.execute()
        current = int(results[1])
        if current >= limit:
            prom_metrics.rate_limit_rejected_total.inc()
            oldest = await redis.zrange(bucket, 0, 0, withscores=True)
            retry_after = 1
            if oldest:
                retry_after = max(
                    1,
                    int(math.ceil(window - (now - float(oldest[0][1])))),
                )
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )

        await redis.zadd(bucket, {member: now})
        await redis.expire(bucket, int(window) + 5)

        return await call_next(request)
