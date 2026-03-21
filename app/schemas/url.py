import re
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator

_ALIAS_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")


class ShortenRequest(BaseModel):
    url: HttpUrl
    custom_alias: str | None = None
    ttl_hours: int | None = Field(default=None, ge=1, le=87600)

    @field_validator("custom_alias")
    @classmethod
    def validate_alias(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _ALIAS_RE.fullmatch(v):
            raise ValueError(
                "custom_alias must be 3-20 characters: letters, digits, underscore, hyphen"
            )
        return v


class ShortenResponse(BaseModel):
    short_url: str
    code: str
    expires_at: datetime | None
