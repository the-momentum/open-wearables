from enum import StrEnum


class WorkoutIntensity(StrEnum):
    """Unified subjective intensity of a workout, independent of the reporting provider.

    Providers each expose their own vocabulary for this:
    Oura: easy / moderate / hard
    """

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    UNKNOWN = "unknown"
