from enum import StrEnum


class SourceSelection(StrEnum):
    """Which data sources a read returns when a user's series come from more than one."""

    ALL = "all"
    # One source per series type for the whole requested range.
    PER_RANGE = "per_range"
    # One source per series type and period: the day for day, week and month reads, the bucket below a day.
    PER_PERIOD = "per_period"
    # Event records (sleep, workouts) only: a session is dropped where a better-ranked source's sessions cover it.
    PER_SESSION = "per_session"
    # Day, week and month reads only: steps, distance, active energy and other movement series merged across sources
    # per day, each moment counted once from the best-ranked source recording it; other series as per_period.
    RECONCILE = "reconcile"
