from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.redirect import router as redirect_router
from app.api.v1.router import api_router
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings()
    yield


app = FastAPI(title="URLShort", lifespan=lifespan)

app.include_router(api_router, prefix="/api/v1")
app.include_router(redirect_router)
