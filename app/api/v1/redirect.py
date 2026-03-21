from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal, get_db
from app.services import analytics

router = APIRouter()

_RESERVED = frozenset({"api"})


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

    row = await analytics.get_active_url_by_code(db, code)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")

    client = request.client
    ip = client.host if client else "0.0.0.0"
    ua = request.headers.get("user-agent") or ""
    ref = request.headers.get("referer")

    background_tasks.add_task(
        _record_click_background,
        row.id,
        ip,
        ua,
        ref,
    )

    return RedirectResponse(url=row.original_url, status_code=301)
