# ruff: noqa: N815

from __future__ import annotations

from pydantic import BaseModel, Field

from .record_import import RecordJSON as HKRecordJSON
from .workout_import import WorkoutJSON as HKWorkoutJSON


class AppleHealthDataRequest(BaseModel):
    """Schema for Apple HealthKit data import via SDK.

    This schema represents the structure of health data exported from Apple HealthKit
    and sent to the SDK sync endpoint. The data is processed asynchronously via Celery.

    Structure:
    - `records`: Time-series measurements (heart rate, steps, distance, etc.)
    - `sleep`: Sleep phase records (in bed, awake, light, deep, REM)
    - `workouts`: Exercise/workout sessions with statistics

    All fields are optional - you can send any combination of records, sleep, and workouts.
    """

    data: DataSection = Field(
        ...,
        description="Root data section containing health records, sleep data, and workouts",
    )


class DataSection(BaseModel):
    """Data section containing health records, sleep, and workouts."""

    records: list[HKRecordJSON] = Field(
        default_factory=list,
        description="Time-series health measurements (heart rate, steps, distance, etc.)",
    )
    sleep: list[HKRecordJSON] = Field(
        default_factory=list,
        description="Sleep phase records. Each record's `value` field contains the sleep phase as integer: "
        "0=IN_BED, 1=ASLEEP_UNSPECIFIED, 2=AWAKE, 3=ASLEEP_CORE (light), 4=ASLEEP_DEEP, 5=ASLEEP_REM",
    )
    workouts: list[HKWorkoutJSON] = Field(
        default_factory=list,
        description="Exercise/workout sessions with optional statistics (distance, heart rate, calories, etc.)",
    )

    class Config:
        json_schema_extra = {
            "example": {
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
