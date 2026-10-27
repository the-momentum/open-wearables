from enum import StrEnum


class SourceSelection(StrEnum):
    """Which data sources a read returns when a user's series come from more than one."""

    ALL = "all"
    # One source per series type for the whole requested range.
    PER_RANGE = "per_range"
    # One source per series type and period: the day for day, week and month reads, the bucket below a day.
    PER_PERIOD = "per_period"
    # Event records (sleep, workouts) only: a session is dropped where a better-ranked source recorded the same one.
    PER_SESSION = "per_session"
