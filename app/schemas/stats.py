from datetime import date, datetime

from pydantic import BaseModel, Field


class DayStat(BaseModel):
    date: date
    count: int


class RefererStat(BaseModel):
    referer: str
    count: int


class CountryStat(BaseModel):
    country: str
    count: int


class DeviceBreakdown(BaseModel):
    mobile: int = Field(default=0, ge=0)
    desktop: int = Field(default=0, ge=0)
    tablet: int = Field(default=0, ge=0)
    bot: int = Field(default=0, ge=0)


class StatsResponse(BaseModel):
    total_clicks: int
    clicks_by_day: list[DayStat]
    top_referers: list[RefererStat]
    top_countries: list[CountryStat]
    device_breakdown: DeviceBreakdown
    created_at: datetime
    original_url: str
