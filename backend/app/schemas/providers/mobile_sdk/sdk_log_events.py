# ruff: noqa: N815

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class DataTypeCount(BaseModel):
    """Count of records for a specific data type."""

    type: str
    count: int = Field(ge=0)


class TimeRange(BaseModel):
    startDate: datetime
    endDate: datetime


class HistoricalDataSyncStartEvent(BaseModel):
    eventType: Literal["historical_data_sync_start"]
    timestamp: datetime
    dataTypeCounts: list[DataTypeCount] = Field(default_factory=list)
    timeRange: TimeRange | None = None


class HistoricalDataTypeSyncEndEvent(BaseModel):
    eventType: Literal["historical_data_type_sync_end"]
    timestamp: datetime
    dataType: str
    success: bool
    recordCount: int | None = None
    durationMs: int | None = None


class DeviceStateEvent(BaseModel):
    eventType: Literal["device_state"]
    timestamp: datetime
    batteryLevel: float | None = Field(None, ge=0.0, le=1.0)
    batteryState: str | None = None
    isLowPowerMode: bool | None = None
    thermalState: str | None = None
    taskType: str | None = None
    availableRamBytes: int | None = None
    totalRamBytes: int | None = None


SDKLogEvent = Annotated[
    HistoricalDataSyncStartEvent | HistoricalDataTypeSyncEndEvent | DeviceStateEvent,
    Field(discriminator="eventType"),
]


class SDKLogRequest(BaseModel):
    """Top-level request for SDK log events endpoint."""

    sdkVersion: str
    provider: str | None = None
    events: list[SDKLogEvent] = Field(..., min_length=1, max_length=100)
