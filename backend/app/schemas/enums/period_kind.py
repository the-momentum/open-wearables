from enum import StrEnum


class PeriodKind(StrEnum):
    """Calendar period a SeriesAggregate row covers, bounded by its period_start and period_end."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
