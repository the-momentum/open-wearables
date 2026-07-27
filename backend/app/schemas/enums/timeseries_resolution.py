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
