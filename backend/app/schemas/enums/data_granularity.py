from datetime import timedelta
from enum import StrEnum


class DataGranularity(StrEnum):
    """How finely a provider's 24/7 data is stored.

    DAILY  — one aggregated value per day (server-side rollup).
    HOURLY — one aggregated value per hour (server-side rollup).
    RAW    — every individual reading (no aggregation), where the provider supports it.
    """

    DAILY = "daily"
    HOURLY = "hourly"
    RAW = "raw"


# Aggregation window (seconds) per aggregating granularity.
# Raw is absent intentionally
# Add an entry here when adding a granularity that aggregates.
GRANULARITY_WINDOW_SECONDS: dict[DataGranularity, int] = {
    DataGranularity.DAILY: 86_400,
    DataGranularity.HOURLY: 3_600,
}


class Resolution(StrEnum):
    """Bucket width requested when reading time series. RAW returns stored samples untouched."""

    RAW = "raw"
    ONE_MIN = "1min"
    FIVE_MIN = "5min"
    FIFTEEN_MIN = "15min"
    ONE_HOUR = "1hour"


BUCKET_SIZES: dict[Resolution, timedelta] = {
    Resolution.ONE_MIN: timedelta(minutes=1),
    Resolution.FIVE_MIN: timedelta(minutes=5),
    Resolution.FIFTEEN_MIN: timedelta(minutes=15),
    Resolution.ONE_HOUR: timedelta(hours=1),
}
