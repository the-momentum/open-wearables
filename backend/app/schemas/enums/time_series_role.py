from enum import StrEnum


class TimeSeriesRole(StrEnum):
    """Distinguish provider aggregates from individual time-series readings."""

    MEASUREMENT = "measurement"
    NIGHTLY_AGGREGATE = "nightly_aggregate"
    NIGHTLY_SAMPLE = "nightly_sample"
