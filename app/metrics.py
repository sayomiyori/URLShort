"""Prometheus metrics for URLShort (custom + used with starlette-prometheus /metrics)."""

from __future__ import annotations

import logging
import time
from typing import Literal

from prometheus_client import Counter, Gauge, Histogram

log = logging.getLogger(__name__)

# --- Custom metrics (names match Grafana / user spec) ---

redirects_total = Counter(
    "redirects_total",
    "Redirects by HTTP status and whether response used Redis URL cache",
    labelnames=("status_code", "cached"),
)

short_url_created_total = Counter(
    "short_url_created_total",
    "Successful POST /api/v1/shorten responses",
)

redirect_duration_seconds = Histogram(
    "redirect_duration_seconds",
    "Time spent handling GET /{code} redirect handler (seconds)",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25),
)

cache_operations_total = Counter(
    "cache_operations_total",
    "Redis URL cache lookups",
    labelnames=("result",),
)

cache_hit_ratio = Gauge(
    "cache_hit_ratio",
    "Approximate cache hit ratio (hits / (hits+misses)), refreshed periodically",
)

rate_limit_rejected_total = Counter(
    "rate_limit_rejected_total",
    "429 responses from Redis sliding-window rate limiter",
)

active_urls_total = Gauge(
    "active_urls_total",
    "Count of rows in url where is_active is true",
)

_cache_hit_count = 0
_cache_miss_count = 0


def record_cache_operation(result: Literal["hit", "miss"]) -> None:
    global _cache_hit_count, _cache_miss_count
    cache_operations_total.labels(result=result).inc()
    if result == "hit":
        _cache_hit_count += 1
    else:
        _cache_miss_count += 1


def refresh_cache_hit_ratio_gauge() -> None:
    total = _cache_hit_count + _cache_miss_count
    cache_hit_ratio.set(_cache_hit_count / total if total else 0.0)


def observe_redirect_duration_seconds(start_perf: float) -> None:
    redirect_duration_seconds.observe(time.perf_counter() - start_perf)


def record_redirect(*, status_code: str, cached: str) -> None:
    redirects_total.labels(status_code=status_code, cached=cached).inc()
