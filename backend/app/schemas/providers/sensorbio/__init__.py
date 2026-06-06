"""Pydantic models for Sensor Bio API response validation.

These mirror the Polar pattern (_parse() + typed schema per endpoint) so
malformed payloads are caught at the boundary, logged, and skipped rather
than silently producing None values in DB writes.
"""

from .models import (
    Activity,
    BiometricsRecord,
    ScoresRecord,
    SleepRecord,
    StepDetailMetric,
    StepDetailsResponse,
    WorkoutStats,
)

__all__ = [
    "SleepRecord",
    "ScoresRecord",
    "BiometricsRecord",
    "StepDetailMetric",
    "StepDetailsResponse",
    "WorkoutStats",
    "Activity",
]
