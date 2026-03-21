from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.stats import StatsResponse
from app.services import analytics

router = APIRouter()


@router.get("/stats/{code}", response_model=StatsResponse)
async def stats(
    code: str,
    db: AsyncSession = Depends(get_db),
) -> StatsResponse:
    out = await analytics.get_stats(db, code)
    if out is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return out
