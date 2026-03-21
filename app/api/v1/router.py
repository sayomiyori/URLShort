from fastapi import APIRouter

from app.api.v1 import shorten, stats

api_router = APIRouter()
api_router.include_router(shorten.router, tags=["shorten"])
api_router.include_router(stats.router, tags=["stats"])
