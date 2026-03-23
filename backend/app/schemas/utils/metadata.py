from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SourceMetadata(BaseModel):
    provider: str = Field(..., example="apple_health")
    device: str | None = Field(None, example="Apple Watch Series 9")


class TimeseriesMetadata(BaseModel):
    resolution: Literal["raw", "1min", "5min", "15min", "1hour"] | None = None
    sample_count: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
