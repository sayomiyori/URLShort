from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.url import ShortenRequest, ShortenResponse
from app.services import shortener

router = APIRouter()


@router.post("/shorten", response_model=ShortenResponse)
async def shorten(
    body: ShortenRequest,
    db: AsyncSession = Depends(get_db),
) -> ShortenResponse:
    try:
        return await shortener.shorten_url(
            db,
            original_url=str(body.url),
            custom_alias=body.custom_alias,
            ttl_hours=body.ttl_hours,
        )
    except ValueError as e:
        if str(e) == "alias_taken":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="custom_alias already exists",
            ) from e
        raise

