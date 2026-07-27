from enum import StrEnum


class TimeseriesResolution(StrEnum):
    """Downsampling resolution for time-series reads.

    RAW returns the stored samples unchanged. Every other value buckets samples
    into fixed UTC-aligned intervals (bucket start = unix epoch multiple of the
    interval) and aggregates each bucket before returning it.
    """

    RAW = "raw"
    ONE_MINUTE = "1min"
    FIVE_MINUTES = "5min"
    FIFTEEN_MINUTES = "15min"
    ONE_HOUR = "1hour"


# Bucket width (seconds) per aggregating resolution.
# Raw is absent intentionally — it performs no aggregation.
RESOLUTION_BUCKET_SECONDS: dict[TimeseriesResolution, int] = {
    TimeseriesResolution.ONE_MINUTE: 60,
    TimeseriesResolution.FIVE_MINUTES: 300,
    TimeseriesResolution.FIFTEEN_MINUTES: 900,
    TimeseriesResolution.ONE_HOUR: 3_600,
}

# Maximum queryable span (days) per aggregating resolution.
# Downsampling loads every raw row of the requested range into memory before
# bucketing, so the span is capped relative to the bucket width: finer buckets
# mean more rows per day, hence a shorter allowed span. Each cap allows roughly
# 45k buckets (1min: 31d x 1440/day ~= 44.6k; 5min/15min: 93d x 288/96 per day
# ~= 26.8k/8.9k; 1hour: 366d x 24/day ~= 8.8k), keeping memory usage bounded
# while covering realistic dashboards (a month of minute data, a quarter of
# 5/15-minute data, a leap year of hourly data).
# Raw is absent intentionally — it paginates at the database level.
RESOLUTION_MAX_RANGE_DAYS: dict[TimeseriesResolution, int] = {
    TimeseriesResolution.ONE_MINUTE: 31,
    TimeseriesResolution.FIVE_MINUTES: 93,
    TimeseriesResolution.FIFTEEN_MINUTES: 93,
    TimeseriesResolution.ONE_HOUR: 366,
}
