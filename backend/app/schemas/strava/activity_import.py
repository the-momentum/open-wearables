from pydantic import BaseModel, ConfigDict


class ActivityJSON(BaseModel):
    """Strava activity data from API responses or webhook fetches.

    Based on Strava API v3 DetailedActivity schema.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Required fields
    id: int
    name: str
    type: str  # e.g. "Run", "Ride", "Swim"
    sport_type: str  # More specific, e.g. "TrailRun", "MountainBikeRide"
    start_date: str  # ISO 8601 UTC
    elapsed_time: int  # seconds

    # Optional fields
    distance: float | None = None  # meters
    moving_time: int | None = None  # seconds
    total_elevation_gain: float | None = None  # meters
    elev_high: float | None = None  # meters
    elev_low: float | None = None  # meters

    # Heart rate
    average_heartrate: float | None = None
    max_heartrate: float | None = None
    has_heartrate: bool | None = None

    # Speed
    average_speed: float | None = None  # meters/second
    max_speed: float | None = None  # meters/second

    # Power
    average_watts: float | None = None
    max_watts: int | None = None
    weighted_average_watts: int | None = None
    device_watts: bool | None = None

    # Calories & energy
    kilojoules: float | None = None
    calories: float | None = None

    # Athlete info
    athlete: dict | None = None  # {"id": 12345}

    # Metadata
    gear_id: str | None = None
    device_name: str | None = None
    trainer: bool | None = None
    commute: bool | None = None
    manual: bool | None = None
    private: bool | None = None

    # Timestamps
    start_date_local: str | None = None  # ISO 8601 local
    timezone: str | None = None
    utc_offset: float | None = None
