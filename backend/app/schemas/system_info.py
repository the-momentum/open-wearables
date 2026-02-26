from pydantic import BaseModel


class CountWithGrowth(BaseModel):
    """Count with weekly growth percentage."""

    count: int
    weekly_growth: float


class SeriesTypeMetric(BaseModel):
    """Series type metric information."""

    series_type: str
    count: int


class WorkoutTypeMetric(BaseModel):
    """Workout type metric information."""

    workout_type: str | None
    count: int


class DataPointsInfo(BaseModel):
    """Data points information."""

    count: int
    weekly_growth: float
    top_series_types: list[SeriesTypeMetric]
    top_workout_types: list[WorkoutTypeMetric]


class SystemInfoResponse(BaseModel):
    """Dashboard system information response."""

    total_users: CountWithGrowth
    active_conn: CountWithGrowth
    data_points: DataPointsInfo


class EventTypeMetric(BaseModel):
    """Event record metric grouped by category and type."""

    category: str
    type: str | None
    count: int


class UserDataStats(BaseModel):
    """Per-user data type counts and totals."""

    total_data_points: int
    series_types: list[SeriesTypeMetric]
    event_types: list[EventTypeMetric]
