from pydantic import BaseModel


class WhoopWorkoutScoreJSON(BaseModel):
    """Whoop workout score data."""

    strain: float | None = None
    average_heart_rate: int | None = None
    max_heart_rate: int | None = None
    kilojoule: float | None = None
    percent_recorded: int | None = None
    distance_meter: float | None = None
    altitude_gain_meter: float | None = None
    altitude_change_meter: float | None = None
    zone_durations: dict[str, int] | None = None  # zone_zero_milli, zone_one_milli, etc.


class WhoopWorkoutJSON(BaseModel):
    """Whoop workout data from API."""

    id: str  # UUID
    v1_id: int | None = None
    user_id: int
    created_at: str
    updated_at: str
    start: str  # ISO 8601
    end: str  # ISO 8601
    timezone_offset: str | None = None
    sport_name: str | None = None
    sport_id: int | None = None
    score_state: str | None = None  # "SCORED", "PENDING", etc.
    score: WhoopWorkoutScoreJSON | None = None


class WhoopWorkoutCollectionJSON(BaseModel):
    """Whoop workout collection response."""

    records: list[WhoopWorkoutJSON]
    next_token: str | None = None
