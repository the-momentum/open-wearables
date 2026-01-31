# ruff: noqa: N815

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.constants.series_types.apple import (
    CATEGORY_TYPE_IDENTIFIERS,
    METRIC_TYPE_TO_SERIES_TYPE,
)
from app.constants.workout_types.apple_sdk import SDK_TO_UNIFIED

from .source import SourceInfo

# Extract all valid Apple HealthKit metric type keys for Literal type
# This ensures type safety and OpenAPI documentation
# Includes both quantity types (HKQuantityTypeIdentifier...) and category types (HKCategoryTypeIdentifier...)
_APPLE_METRIC_TYPE_KEYS = tuple(METRIC_TYPE_TO_SERIES_TYPE.keys()) + tuple(CATEGORY_TYPE_IDENTIFIERS)
AppleMetricType = Literal[_APPLE_METRIC_TYPE_KEYS]  # type: ignore[valid-type]

# Extract all valid SDK workout type keys for Literal type
# This ensures type safety and OpenAPI documentation
_SDK_WORKOUT_TYPE_KEYS = tuple(SDK_TO_UNIFIED.keys())
SDKWorkoutType = Literal[_SDK_WORKOUT_TYPE_KEYS]  # type: ignore[valid-type]


class HealthRecord(BaseModel):
    """Schema for JSON import format from HealthKit.

    Represents a single health measurement (heart rate, steps, distance, etc.).
    """

    uuid: str | None = None
    user_id: str | None = None
    type: AppleMetricType | None = None
    startDate: datetime
    endDate: datetime
    unit: str | None
    value: Decimal
    source: SourceInfo | None = None
    recordMetadata: list[dict[str, Any]] | None = None


class WorkoutStatistic(BaseModel):
    """Schema for workout statistic (distance, heart rate, calories, etc.)."""

    type: str
    unit: str
    value: float | int


class Workout(BaseModel):
    """Schema for workout/exercise session from HealthKit."""

    uuid: str | None = None
    user_id: str | None = None
    type: SDKWorkoutType | None = None
    startDate: datetime
    endDate: datetime
    source: SourceInfo | None = None
    workoutStatistics: list[WorkoutStatistic] | None = None


class SyncRequestData(BaseModel):
    """Inner data structure for Apple HealthKit sync request.

    Contains the actual health data arrays.
    """

    records: list[HealthRecord] = Field(
        default_factory=list,
        description="Time-series health measurements (heart rate, steps, distance, etc.)",
    )
    sleep: list[HealthRecord] = Field(
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
