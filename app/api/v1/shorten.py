from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import metrics as prom_metrics
from app.cache import url_cache
from app.db.session import get_db
from app.schemas.url import ShortenRequest, ShortenResponse
from app.services import shortener

router = APIRouter()


@router.post("/shorten", response_model=ShortenResponse)
async def shorten(
    body: ShortenRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ShortenResponse:
    try:
        resp = await shortener.shorten_url(
            db,
            original_url=str(body.url),
            custom_alias=body.custom_alias,
            ttl_hours=body.ttl_hours,
        )
        rredis = getattr(request.app.state, "redis", None)
        background_tasks.add_task(url_cache.invalidate, rredis, resp.code)
        prom_metrics.short_url_created_total.inc()
        return resp
    except ValueError as e:
        if str(e) == "alias_taken":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="custom_alias already exists",
            ) from e
        raise
