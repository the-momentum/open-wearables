from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.enums import TimelineBucket, TimelineGroupBy


class TimelineMetric(StrEnum):
    """What a series counts. Event records (workouts, sleep) join as their own metric."""

    DATA_POINTS = "data_points"


class TimelineSeries(BaseModel):
    key: str
    metric: TimelineMetric = TimelineMetric.DATA_POINTS
    buckets: list[tuple[date, int]] = Field(description="``[bucket_start, count]`` pairs, chronological")


class UserDataTimelineResponse(BaseModel):
    """Per-user data density over time. Sparse: buckets with no data are omitted."""

    bucket: TimelineBucket
    group_by: TimelineGroupBy
    series: list[TimelineSeries] = Field(default_factory=list)
