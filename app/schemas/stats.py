from datetime import date, datetime

from pydantic import BaseModel


class DayCount(BaseModel):
    day: date
    count: int


class NamedCount(BaseModel):
    name: str
    count: int


class StatsResponse(BaseModel):
    total_clicks: int
    clicks_by_day: list[DayCount]
    top_referers: list[NamedCount]
    top_countries: list[NamedCount]
    top_devices: list[NamedCount]
    created_at: datetime
    original_url: str
