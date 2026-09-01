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
