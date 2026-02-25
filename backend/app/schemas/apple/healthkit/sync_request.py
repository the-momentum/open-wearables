# ruff: noqa: N815

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.constants.series_types.apple import AppleMetricType, SleepPhase, WorkoutStatisticType
from app.constants.workout_types import SDKWorkoutType


class DeviceType(StrEnum):
    """Device type for HealthKit records."""

    PHONE = "phone"
    WATCH = "watch"
    SCALE = "scale"
    RING = "ring"
    FITNESS_BAND = "fitness_band"
    CHEST_STRAP = "chest_strap"
    HEAD_MOUNTED = "head_mounted"
    SMART_DISPLAY = "smart_display"
    UNKNOWN = "unknown"

class RecordingMethod(StrEnum):
    """Recording method for HealthKit records."""

    ACTIVE = "active"
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class OSVersion(BaseModel):
    """Operating system version info from HealthKit source."""

    model_config = ConfigDict(populate_by_name=True)

    major_version: int = Field(alias="majorVersion")
    minor_version: int = Field(alias="minorVersion")
    patch_version: int = Field(alias="patchVersion")


class SourceInfo(BaseModel):
    """Source/device information for HealthKit records."""

    model_config = ConfigDict(populate_by_name=True)

    app_id: str | None = Field(default=None, alias="appId")
    name: str | None = None
    bundle_identifier: str | None = Field(default=None, alias="bundleIdentifier")
    version: str | None = None
    product_type: str | None = Field(default=None, alias="productType")
    operating_system_version: OSVersion | None = Field(default=None, alias="operatingSystemVersion")
    device_id: str | None = Field(default=None, alias="deviceId")
    device_name: str | None = Field(default=None, alias="deviceName")
    device_manufacturer: str | None = Field(default=None, alias="deviceManufacturer")
    device_type: DeviceType | str | None = Field(default=None, alias="deviceType")
    device_model: str | None = Field(default=None, alias="deviceModel")
    device_hardware_version: str | None = Field(default=None, alias="deviceHardwareVersion")
    device_software_version: str | None = Field(default=None, alias="deviceSoftwareVersion")
    recording_method: RecordingMethod | str | None = Field(default=None, alias="recordingMethod")


class MetricRecord(BaseModel):
    """Health metric record from HealthKit (heart rate, steps, distance, etc.)."""

    id: str | None = None
    parentId: str | None = None
    type: AppleMetricType | str | None = None
    startDate: datetime
    endDate: datetime
    zoneOffset: str | None = None
    source: SourceInfo | None = None
    value: Decimal
    unit: str | None
    metadata: list[dict[str, Any]] | dict[str, Any] | None = None


class SleepRecord(BaseModel):
    """Sleep analysis record from HealthKit."""

    id: str | None = None
    parentId: str | None = None
    stage: SleepPhase | str
    startDate: datetime
    endDate: datetime
    zoneOffset: str | None = None
    source: SourceInfo | None = None
    values: list[dict[str, Any]] | None = None
    metadata: list[dict[str, Any]] | dict[str, Any] | None = None


class WorkoutStatistic(BaseModel):
    """Schema for workout statistic (distance, heart rate, calories, etc.)."""

    type: WorkoutStatisticType | str
    unit: str
    value: float | int


class Workout(BaseModel):
    """Schema for workout/exercise session from HealthKit."""

    id: str | None = None
    parentId: str | None = None
    type: SDKWorkoutType | str | None = None
    startDate: datetime
    endDate: datetime
    zoneOffset: str | None = None
    source: SourceInfo | None = None
    title: str | None = None
    notes: str | None = None
    values: list[WorkoutStatistic] | None = None

    # everything below is unused for now
    segments: list[dict[str, Any]] | None = None
    laps: list[dict[str, Any]] | None = None
    route: list[dict[str, Any]] | None = None
    samples: list[dict[str, Any]] | None = None
    metadata: list[dict[str, Any]] | dict[str, Any] | None = None


class SyncRequestData(BaseModel):
    """Inner data structure for Apple HealthKit sync request.

    Contains the actual health data arrays.
    """

    records: list[MetricRecord] = Field(
        default_factory=list,
        description="Time-series health measurements (heart rate, steps, distance, etc.)",
    )
    sleep: list[SleepRecord] = Field(
        default_factory=list,
        description="Sleep phase records. Each record's `value` field contains the sleep phase as integer: "
        "0=IN_BED, 1=ASLEEP_UNSPECIFIED, 2=AWAKE, 3=ASLEEP_CORE (light), 4=ASLEEP_DEEP, 5=ASLEEP_REM",
    )
    workouts: list[Workout] = Field(
        default_factory=list,
        description="Exercise/workout sessions with optional statistics (distance, heart rate, calories, etc.)",
    )


class SyncRequest(BaseModel):
    """Schema for Apple HealthKit data import via SDK.

    This schema represents the structure of health data exported from Apple HealthKit
    and sent to the SDK sync endpoint. The data is processed asynchronously via Celery.

    Structure:
    - `data.records`: Time-series measurements (heart rate, steps, distance, etc.)
    - `data.sleep`: Sleep phase records (in bed, awake, light, deep, REM)
    - `data.workouts`: Exercise/workout sessions with statistics

    All fields within `data` are optional - you can send any combination of records, sleep, and workouts.
    """

    provider: str
    sdkVersion: str
    syncTimestamp: datetime
    data: SyncRequestData = Field(
        default_factory=SyncRequestData,
        description="Container for health data arrays (records, sleep, workouts)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "provider": "samsung_health",
                "sdkVersion": "0.1.0",
                "syncTimestamp": "2026-02-24T10:00:00Z",
                "data": {
                    "records": [
                        {
                            "id": "abc-xyz-123-sys",
                            "type": "BLOOD_PRESSURE_SYSTOLIC",
                            "startDate": "2026-02-24T08:30:00Z",
                            "endDate": "2026-02-24T08:30:00Z",
                            "zoneOffset": "+01:00",
                            "source": {
                                "appId": "com.sec.android.app.shealth",
                                "deviceId": "R9ZW30ABC12",
                                "deviceName": "Galaxy Watch7",
                                "deviceManufacturer": "Samsung",
                                "deviceModel": "SM-R960",
                                "deviceType": "watch",
                                "recordingMethod": None # null
                            },
                            "value": 122.0,
                            "unit": "mmHg",
                            "parentId": "abc-xyz-123",
                            "metadata": None # null
                        }
                    ],
                    "sleep": [
                        {
                            "id": "slp-001-s0-0",
                            "parentId": "slp-001",
                            "stage": "light",
                            "startDate": "2026-02-23T23:10:00Z",
                            "endDate": "2026-02-24T00:00:00Z",
                            "zoneOffset": "+01:00",
                            "source": {
                            "appId": "com.sec.android.app.shealth",
                            "deviceId": "R9ZW30ABC12",
                            "deviceName": "Galaxy Watch7",
                            "deviceManufacturer": "Samsung",
                            "deviceModel": "SM-R960",
                            "deviceType": "watch",
                            "recordingMethod": None # null
                            },
                            "values": [
                                { "type": "sleepScore", "value": 82, "unit": "score" }
                            ],
                            "metadata": None # null
                        }
                    ],
                    "workouts": [
                        {
                            "id": "wrk-001-s0",
                            "parentId": "wrk-001",
                            "type": "RUNNING",
                            "startDate": "2026-02-24T06:00:00Z",
                            "endDate": "2026-02-24T06:45:00Z",
                            "zoneOffset": "+01:00",
                            "source": {
                                "appId": "com.sec.android.app.shealth",
                                "deviceId": "R9ZW30ABC12",
                                "deviceName": "Galaxy Watch7",
                                "deviceManufacturer": "Samsung",
                                "deviceModel": "SM-R960",
                                "deviceType": "watch",
                                "recordingMethod": None # null
                            },
                            "title": None, # null
                            "notes": "Morning run in the park",
                            "values": [
                                { "type": "duration", "value": 2700000, "unit": "ms" },
                                { "type": "calories", "value": 345.5, "unit": "kcal" },
                                { "type": "distance", "value": 5234.0, "unit": "m" },
                                { "type": "meanHeartRate", "value": 142.3, "unit": "bpm" },
                                { "type": "maxHeartRate", "value": 178.0, "unit": "bpm" },
                                { "type": "minHeartRate", "value": 95.0, "unit": "bpm" },
                                { "type": "meanSpeed", "value": 1.50, "unit": "m/s" },
                                { "type": "maxSpeed", "value": 3.20, "unit": "m/s" },
                                { "type": "meanCadence", "value": 165.0, "unit": "spm" },
                                { "type": "maxCadence", "value": 182.0, "unit": "spm" },
                                { "type": "altitudeGain", "value": 45.0, "unit": "m" },
                                { "type": "altitudeLoss", "value": 42.0, "unit": "m" },
                                { "type": "maxAltitude", "value": 185.0, "unit": "m" },
                                { "type": "minAltitude", "value": 140.0, "unit": "m" },
                                { "type": "vo2Max", "value": 42.5, "unit": "mL/kg/min" }
                            ],
                            "segments": None, # null
                            "laps": None, # null
                            "route": [
                            {
                                "timestamp": "2026-02-24T06:01:00Z",
                                "latitude": 52.229676,
                                "longitude": 21.012229,
                                "altitudeM": 142.0,
                                "horizontalAccuracyM": 3.5,
                                "verticalAccuracyM": None # null
                            }
                            ],
                            "samples": [
                                { "timestamp": "2026-02-24T06:01:00Z", "type": "heartRate", "value": 110.0, "unit": "bpm" },
                                { "timestamp": "2026-02-24T06:01:00Z", "type": "cadence", "value": 155.0, "unit": "spm" },
                                { "timestamp": "2026-02-24T06:01:00Z", "type": "speed", "value": 1.8, "unit": "m/s" }
                            ],
                            "metadata": None # null
                        }
                    ],
                }
            }
        }

