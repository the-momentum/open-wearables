from pydantic import BaseModel


class MetricCount(BaseModel):
    """A single count metric."""

    count: int


class DataPointsInfo(BaseModel):
    """Data points information.

    ``count`` is the live (hot) ``data_point_series`` table; ``archived`` is the separate archive
    table. Both are approximate on a cold cache / from planner statistics.
    """

    count: int
    archived: int


class EventRecordsInfo(BaseModel):
    """Event record counts with a breakdown by category."""

    count: int
    workouts: int
    sleep: int
    menstrual_cycles: int


class ProviderConnectionCount(BaseModel):
    provider: str
    count: int


class ConnectionsCoverage(BaseModel):
    users_with_active: int
    users_with_multi_active: int
    top_providers: list[ProviderConnectionCount]


class SystemInfoResponse(BaseModel):
    """Dashboard system information response."""

    total_users: MetricCount
    active_conn: MetricCount
    data_points: DataPointsInfo
    event_records: EventRecordsInfo
    connections_coverage: ConnectionsCoverage
