from enum import StrEnum


class WorkoutIntensity(StrEnum):
    """Unified subjective intensity of a workout, independent of the reporting provider."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    UNKNOWN = "unknown"
