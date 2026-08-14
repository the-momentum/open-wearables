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
    # startDate is absent when the SDK syncs the full available history (no syncDaysBack
    # limit configured) — both the iOS and Android SDKs omit it in that case.
    startDate: datetime | None = None
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
    # False means the export ended with this type unfinished, which is not the same as a
    # failure. A genuine on-device error carries errorCode as well.
    success: bool
    recordCount: int | None = None
    # Measured from the start of the whole run, so every type in a run reports the same
    # value. Not usable for per-type timing until the SDK measures it per type.
    durationMs: int | None = None
    errorCode: str | None = None
    errorMessage: str | None = None
    # Span this type actually covered, which the run-level range cannot give us: HealthKit
    # grants authorization per type and the device may hold less history for some of them.
    # Absent on SDK versions that predate it, and coverage stays unknown rather than guessed.
    timeRange: TimeRange | None = None


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
    syncSessionId: str | None = Field(
        None,
        description=(
            "Device-generated id, stable for one historical export and shared with the "
            "sync endpoint, so log events can be attached to the run their data belongs to."
        ),
    )
    events: list[SDKLogEvent] = Field(..., min_length=1, max_length=100)
