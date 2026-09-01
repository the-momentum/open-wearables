from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field

from app.constants.devices_map import resolve_device_name
from app.schemas.enums import DeviceType


class SourceMetadata(BaseModel):
    # ``provider`` is the integration the data arrived through (apple, garmin, ...).
    # ``source`` is the writer inside that integration - a third-party app name for
    # HealthKit/Health Connect data ("Connect", "Zepp Life"), or the provider key
    # itself for native API integrations.
    provider: str = Field(..., example="apple")
    source: str | None = Field(None, example="Connect")
    device: str | None = Field(None, example="iPhone15,2")
    device_type: DeviceType | None = Field(None, example="phone")

    @computed_field
    @property
    def device_name(self) -> str | None:
        """Marketing name for ``device``, derived so it cannot drift from the raw model."""
        return resolve_device_name(self.device)


class TimeseriesMetadata(BaseModel):
    resolution: Literal["raw", "1min", "5min", "15min", "1hour"] | None = None
    sample_count: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
