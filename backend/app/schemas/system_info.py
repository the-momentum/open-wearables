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
