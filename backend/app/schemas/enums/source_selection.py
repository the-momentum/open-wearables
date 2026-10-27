from enum import StrEnum


class SourceSelection(StrEnum):
    """Which data sources a read returns when a user's series come from more than one."""

    ALL = "all"
    # One source per series type for the whole requested range.
    PER_RANGE = "per_range"
    # One source per series type and day, or per bucket below a day.
    PER_DAY = "per_day"
