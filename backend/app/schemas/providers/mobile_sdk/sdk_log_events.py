# ruff: noqa: N815

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class SDKLogEventType(StrEnum):
    """Discriminator values for the SDK log event union.

    Checking eventType rather than the class keeps a future member from being matched by
    one of its base classes.
    """

    HISTORICAL_SYNC_START = "historical_data_sync_start"
    HISTORICAL_TYPE_SYNC_END = "historical_data_type_sync_end"
    DEVICE_STATE = "device_state"


class DataTypeCount(BaseModel):
    """Count of records for a specific data type."""

    type: str
    count: int = Field(ge=0)


class TimeRange(BaseModel):
    # Absent when the SDK exports full history rather than a bounded window.
    startDate: datetime | None = None
    endDate: datetime


class HistoricalDataSyncStartEvent(BaseModel):
    eventType: Literal[SDKLogEventType.HISTORICAL_SYNC_START]
    timestamp: datetime
    dataTypeCounts: list[DataTypeCount] = Field(default_factory=list)
    timeRange: TimeRange | None = None


class HistoricalDataTypeSyncEndEvent(BaseModel):
    eventType: Literal[SDKLogEventType.HISTORICAL_TYPE_SYNC_END]
    timestamp: datetime
    dataType: str
    # False means unfinished, not failed; a genuine error also carries errorCode.
    success: bool
    recordCount: int | None = None
    # Measured from the start of the whole run, so every type reports the same value.
    durationMs: int | None = None
    errorCode: str | None = None
    errorMessage: str | None = None
    # Span this type covered. Absent on SDK versions that predate it.
    timeRange: TimeRange | None = None


class DeviceStateEvent(BaseModel):
    eventType: Literal[SDKLogEventType.DEVICE_STATE]
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
    syncSessionId: str | None = Field(
        None,
        description="Device-generated id, stable for one historical export and shared with the sync endpoint.",
    )
    events: list[SDKLogEvent] = Field(..., min_length=1, max_length=100)
