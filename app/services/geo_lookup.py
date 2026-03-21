"""MaxMind GeoLite2 City lookup (optional if .mmdb missing)."""

from __future__ import annotations

import os
from functools import lru_cache

import geoip2.database
import geoip2.errors

from app.config import get_settings


@lru_cache(maxsize=1)
def _reader_for_path(path: str) -> geoip2.database.Reader:
    return geoip2.database.Reader(path)


def _db_path() -> str | None:
    p = (get_settings().maxmind_city_db_path or "").strip()
    if not p:
        return None
    return p if os.path.isfile(p) else None


def lookup_geo(ip: str) -> tuple[str | None, str | None]:
    path = _db_path()
    if path is None:
        return None, None
    try:
        reader = _reader_for_path(path)
        rec = reader.city(ip)
        country = rec.country.iso_code
        city = rec.city.name
        if city and len(city) > 128:
            city = city[:128]
        return country, city
    except (geoip2.errors.AddressNotFoundError, ValueError, OSError, TypeError):
        return None, None
