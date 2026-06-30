"""Heart-family metrics.

heart-rate / run-vo2-max support rollUp + list; daily-resting-heart-rate and
daily-heart-rate-variability are Daily types (list only). Google reports HRV as RMSSD.

heart-rate and run-vo2-max rollUp values also carry Min/Max alongside the Avg we take;
capturing those would need dedicated SeriesTypes + the multi-series model (future).
"""

from app.schemas.enums import SeriesType
from app.schemas.providers.google import DataTypeMetric, ListSpec, RollupSpec, TimeShape

HEART_METRICS: tuple[DataTypeMetric, ...] = (
    DataTypeMetric(
        "heart-rate",
        SeriesType.heart_rate,
        rollup_spec=RollupSpec("heartRate", "beatsPerMinuteAvg", max_range_days=14),
        list_spec=ListSpec("beatsPerMinute", TimeShape.SAMPLE),
    ),
    DataTypeMetric(
        "run-vo2-max",
        SeriesType.vo2_max,
        rollup_spec=RollupSpec("runVo2Max", "rateAvg"),
        list_spec=ListSpec("runVo2Max", TimeShape.SAMPLE),
    ),
    DataTypeMetric(
        "daily-resting-heart-rate",
        SeriesType.resting_heart_rate,
        list_spec=ListSpec("beatsPerMinute", TimeShape.DATE, is_daily_total=True),
    ),
    DataTypeMetric(
        "daily-heart-rate-variability",
        SeriesType.heart_rate_variability_rmssd,
        list_spec=ListSpec("averageHeartRateVariabilityMilliseconds", TimeShape.DATE, is_daily_total=True),
    ),
)
