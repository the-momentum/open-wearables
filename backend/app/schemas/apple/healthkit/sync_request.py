# ruff: noqa: N815

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.constants.series_types import AppleCategoryType, AppleMetricType
from app.constants.workout_statistics import WorkoutStatisticType
from app.constants.workout_types import SDKWorkoutType


class OSVersion(BaseModel):
    """Operating system version info from HealthKit source."""

    model_config = ConfigDict(populate_by_name=True)

    major_version: int = Field(alias="majorVersion")
    minor_version: int = Field(alias="minorVersion")
    patch_version: int = Field(alias="patchVersion")


class SourceInfo(BaseModel):
    """Source/device information for HealthKit records."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    bundle_identifier: str | None = Field(default=None, alias="bundleIdentifier")
    version: str | None = None
    product_type: str | None = Field(default=None, alias="productType")
    operating_system_version: OSVersion | None = Field(default=None, alias="operatingSystemVersion")
    device_name: str | None = Field(default=None, alias="name")
    device_manufacturer: str | None = Field(default=None, alias="deviceManufacturer")
    device_model: str | None = Field(default=None, alias="deviceModel")
    device_hardware_version: str | None = Field(default=None, alias="deviceHardwareVersion")
    device_software_version: str | None = Field(default=None, alias="deviceSoftwareVersion")


class MetricRecord(BaseModel):
    """Health metric record from HealthKit (heart rate, steps, distance, etc.)."""

    uuid: str | None = None
    type: AppleMetricType | None = None
    startDate: datetime
    endDate: datetime
    unit: str | None
    value: Decimal
    source: SourceInfo | None = None
    recordMetadata: list[dict[str, Any]] | None = None


class SleepRecord(BaseModel):
    """Sleep analysis record from HealthKit."""

    uuid: str | None = None
    type: AppleCategoryType | None = None
    startDate: datetime
    endDate: datetime
    unit: str | None
    value: Decimal = Field(
        ge=0,
        le=5,
        description="Sleep phase: 0=IN_BED, 1=ASLEEP_UNSPECIFIED, 2=AWAKE, 3=LIGHT, 4=DEEP, 5=REM",
    )
    source: SourceInfo | None = None
    recordMetadata: list[dict[str, Any]] | None = None


class WorkoutStatistic(BaseModel):
    """Schema for workout statistic (distance, heart rate, calories, etc.)."""

    type: WorkoutStatisticType
    unit: str
    value: float | int


class Workout(BaseModel):
    """Schema for workout/exercise session from HealthKit."""

    uuid: str | None = None
    type: SDKWorkoutType | None = None
    startDate: datetime
    endDate: datetime
    source: SourceInfo | None = None
    workoutStatistics: list[WorkoutStatistic] | None = None


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

    data: SyncRequestData = Field(
        default_factory=SyncRequestData,
        description="Container for health data arrays (records, sleep, workouts)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "data": {
                    "records": [
                        {
                            "uuid": "0F12CD84-80C1-45D2-A0CD-474C144602C4",
                            "type": "HKQuantityTypeIdentifierHeartRate",
                            "unit": "bpm",
                            "value": 72,
                            "startDate": "2024-01-01T03:54:07Z",
                            "endDate": "2024-01-01T03:57:20Z",
                            "source": {
                                "name": "Apple Watch",
                                "deviceModel": "Watch",
                            },
                        }
                    ],
                    "sleep": [
                        {
                            "uuid": "ABC123",
                            "type": "HKCategoryTypeIdentifierSleepAnalysis",
                            "value": 3,
                            "startDate": "2024-01-01T22:00:00Z",
                            "endDate": "2024-01-01T22:30:00Z",
                            "source": {
                                "name": "Apple Watch",
                            },
                        }
                    ],
                    "workouts": [
                        {
                            "uuid": "DEF456",
                            "type": "running",
                            "startDate": "2024-01-01T06:00:00Z",
                            "endDate": "2024-01-01T07:00:00Z",
                            "workoutStatistics": [
                                {"type": "distance", "unit": "m", "value": 5000},
                                {"type": "averageHeartRate", "unit": "bpm", "value": 150},
                            ],
                        }
                    ],
                }
            }
        }
