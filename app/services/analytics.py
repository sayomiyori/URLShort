from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Date, case, cast, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.click import Click
from app.models.url import URL
from app.schemas.stats import DayCount, NamedCount, StatsResponse


def infer_device_type(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if "tablet" in ua or "ipad" in ua:
        return "tablet"
    if "mobile" in ua or "iphone" in ua or ("android" in ua and "mobile" in ua):
        return "mobile"
    if "bot" in ua or "crawler" in ua or "spider" in ua:
        return "bot"
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
    country: str | None = None,
    city: str | None = None,
) -> None:
    device = infer_device_type(user_agent)
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
    t = URL.__table__
    await session.execute(
        update(t).where(t.c.id == url_id).values(click_count=t.c.click_count + 1)
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

    day_col = cast(func.timezone("UTC", Click.clicked_at), Date)
    day_stmt = (
        select(
            day_col.label("d"),
            func.count().label("c"),
        )
        .where(Click.url_id == url_row.id)
        .group_by(day_col)
        .order_by(day_col)
    )
    day_rows = (await session.execute(day_stmt)).all()
    clicks_by_day = [DayCount(day=row.d, count=int(row.c)) for row in day_rows]

    ref_label = case((Click.referer.is_(None), "(none)"), else_=Click.referer)
    ref_stmt = (
        select(ref_label.label("name"), func.count().label("c"))
        .where(Click.url_id == url_row.id)
        .group_by(ref_label)
        .order_by(func.count().desc())
        .limit(10)
    )
    ref_rows = (await session.execute(ref_stmt)).all()
    top_referers = [NamedCount(name=str(row.name), count=int(row.c)) for row in ref_rows]

    country_stmt = (
        select(Click.country.label("name"), func.count().label("c"))
        .where(Click.url_id == url_row.id, Click.country.is_not(None))
        .group_by(Click.country)
        .order_by(func.count().desc())
        .limit(10)
    )
    country_rows = (await session.execute(country_stmt)).all()
    top_countries = [
        NamedCount(name=str(row.name), count=int(row.c)) for row in country_rows
    ]

    dev_stmt = (
        select(Click.device_type.label("name"), func.count().label("c"))
        .where(Click.url_id == url_row.id)
        .group_by(Click.device_type)
        .order_by(func.count().desc())
        .limit(10)
    )
    dev_rows = (await session.execute(dev_stmt)).all()
    top_devices = [NamedCount(name=str(row.name), count=int(row.c)) for row in dev_rows]

    created = url_row.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)

    return StatsResponse(
        total_clicks=total,
        clicks_by_day=clicks_by_day,
        top_referers=top_referers,
        top_countries=top_countries,
        top_devices=top_devices,
        created_at=created,
        original_url=url_row.original_url,
    )
