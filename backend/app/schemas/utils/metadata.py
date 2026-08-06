from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.enums import TimeseriesResolution


class SourceMetadata(BaseModel):
    provider: str = Field(..., example="apple_health")
    device: str | None = Field(None, example="Apple Watch Series 9")


class TimeseriesMetadata(BaseModel):
    resolution: TimeseriesResolution | None = None
    sample_count: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
