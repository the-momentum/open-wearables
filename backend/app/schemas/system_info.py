from pydantic import BaseModel


class CountWithGrowth(BaseModel):
    """Count with weekly growth percentage."""

    count: int
    weekly_growth: float


class DataPointsInfo(BaseModel):
    """Data points information."""

    count: int
    weekly_growth: float


class SystemInfoResponse(BaseModel):
    """Dashboard system information response."""

    total_users: CountWithGrowth
    active_conn: CountWithGrowth
    data_points: DataPointsInfo
