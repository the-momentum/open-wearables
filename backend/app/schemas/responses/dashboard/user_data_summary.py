from pydantic import BaseModel


class ProviderDataCount(BaseModel):
    """Data counts for a single provider."""

    provider: str
    data_points: int
    series_counts: dict[str, int]
    workout_count: int
    sleep_count: int


class UserDataSummaryResponse(BaseModel):
    """Per-user data summary with counts by type and provider."""

    user_id: str
    total_data_points: int
    total_workouts: int
    total_sleep_events: int
    series_type_counts: dict[str, int]
    workout_type_counts: dict[str, int]
    by_provider: list[ProviderDataCount]
