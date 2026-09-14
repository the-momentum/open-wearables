from enum import StrEnum


class TimelineBucket(StrEnum):
    """Width of one bucket in a per-user data timeline."""

    DAY = "day"
    WEEK = "week"


class TimelineGroupBy(StrEnum):
    """What a timeline series is keyed by."""

    PROVIDER = "provider"
    SERIES_TYPE = "series_type"
