from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from user_agents import parse as ua_parse

from app.models.click import Click
from app.models.url import URL
from app.schemas.stats import (
    CountryStat,
    DayStat,
    DeviceBreakdown,
    RefererStat,
    StatsResponse,
)
from app.services.geo_lookup import lookup_geo


def device_type_from_user_agent(user_agent: str) -> str:
    ua = ua_parse(user_agent or "")
    if ua.is_bot:
        return "bot"
    if ua.is_tablet:
        return "tablet"
    if ua.is_mobile:
        return "mobile"
    return "desktop"


async def get_active_url_by_code(session: AsyncSession, code: str) -> URL | None:
    r = await session.execute(select(URL).where(URL.short_code == code))
    row = r.scalar_one_or_none()
    if row is None or not row.is_active:
        return None
    now = datetime.now(timezone.utc)
    if row.expires_at is not None and row.expires_at < now:
        return None
    return row


async def record_click(
    session: AsyncSession,
    *,
    url_id: int,
    ip_address: str,
    user_agent: str,
    referer: str | None,
) -> None:
    country, city = lookup_geo(ip_address)
    device = device_type_from_user_agent(user_agent)
    session.add(
        Click(
            url_id=url_id,
            ip_address=ip_address,
            user_agent=user_agent,
            referer=referer,
            country=country,
            city=city,
            device_type=device,
        )
    )


async def get_stats(session: AsyncSession, code: str) -> StatsResponse | None:
    r = await session.execute(select(URL).where(URL.short_code == code))
    url_row = r.scalar_one_or_none()
    if url_row is None:
        return None

    total_r = await session.execute(
        select(func.count()).select_from(Click).where(Click.url_id == url_row.id)
    )
    total = int(total_r.scalar_one() or 0)

    now = datetime.now(timezone.utc)
    end_d = now.date()
    start_d = end_d - timedelta(days=29)
    start_ts = datetime.combine(start_d, time.min, tzinfo=timezone.utc)

    day_col = cast(func.timezone("UTC", Click.clicked_at), Date)
    day_stmt = (
        select(day_col.label("d"), func.count().label("c"))
        .where(
            Click.url_id == url_row.id,
            Click.clicked_at >= start_ts,
        )
        .group_by(day_col)
    )
    day_rows = (await session.execute(day_stmt)).all()
    counts_by_day = {row.d: int(row.c) for row in day_rows}
    clicks_by_day: list[DayStat] = []
    for i in range(30):
        d = start_d + timedelta(days=i)
        clicks_by_day.append(DayStat(date=d, count=counts_by_day.get(d, 0)))

    ref_label = case((Click.referer.is_(None), "(none)"), else_=Click.referer)
    ref_stmt = (
        select(ref_label.label("ref"), func.count().label("c"))
        .where(Click.url_id == url_row.id)
        .group_by(ref_label)
        .order_by(func.count().desc())
        .limit(10)
    )
    ref_rows = (await session.execute(ref_stmt)).all()
    top_referers = [
        RefererStat(referer=str(row.ref), count=int(row.c)) for row in ref_rows
    ]

    country_stmt = (
        select(Click.country.label("c"), func.count().label("n"))
        .where(Click.url_id == url_row.id, Click.country.is_not(None))
        .group_by(Click.country)
        .order_by(func.count().desc())
        .limit(10)
    )
    country_rows = (await session.execute(country_stmt)).all()
    top_countries = [
        CountryStat(country=str(row.c), count=int(row.n)) for row in country_rows
    ]

    dev_stmt = (
        select(Click.device_type.label("dt"), func.count().label("n"))
        .where(Click.url_id == url_row.id)
        .group_by(Click.device_type)
    )
    dev_rows = (await session.execute(dev_stmt)).all()
    parts = {k: 0 for k in ("mobile", "desktop", "tablet", "bot")}
    for row in dev_rows:
        k = str(row.dt)
        if k in parts:
            parts[k] = int(row.n)
    breakdown = DeviceBreakdown(**parts)

    created = url_row.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)

    return StatsResponse(
        total_clicks=total,
        clicks_by_day=clicks_by_day,
        top_referers=top_referers,
        top_countries=top_countries,
        device_breakdown=breakdown,
        created_at=created,
        original_url=url_row.original_url,
    )
