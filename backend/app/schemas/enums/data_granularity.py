from enum import StrEnum


class DataGranularity(StrEnum):
    """How finely a provider's 24/7 data is stored.

    DAILY  — one aggregated value per day (server-side rollup, default).
    HOURLY — one aggregated value per hour (server-side rollup).
    RAW    — every individual reading (no aggregation), where the provider supports it.
    """

    DAILY = "daily"
    HOURLY = "hourly"
    RAW = "raw"
