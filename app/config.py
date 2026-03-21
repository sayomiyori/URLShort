from functools import lru_cache

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        ...,
        description="Async SQLAlchemy URL, e.g. postgresql+asyncpg://user:pass@host:5432/db",
    )
    alembic_database_url: str | None = Field(
        default=None,
        description="Sync URL for Alembic (postgresql+psycopg://...). Defaults from database_url.",
    )
    public_base_url: AnyUrl = Field(
        default="http://localhost:8000",
        description="Origin used to build short_url in API responses",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def sync_database_url() -> str:
    s = get_settings()
    if s.alembic_database_url:
        return s.alembic_database_url
    url = s.database_url
    if "+asyncpg" in url:
        return url.replace("+asyncpg", "+psycopg", 1)
    return url
