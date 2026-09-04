from enum import StrEnum


class EntrySource(StrEnum):
    """Unified provenance of a workout record, independent of the reporting provider.

    Providers each expose their own vocabulary for this:
    Oura: manual / autodetected / confirmed / workout_heart_rate
    Garmin: manual / isWebUpload flags
    Strava: manual / auto flags
    """

    MANUAL = "manual"
    AUTOMATIC = "automatic"
    UNKNOWN = "unknown"
