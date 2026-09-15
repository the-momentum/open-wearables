"""Heart-family metrics.

heart-rate / run-vo2-max support rollUp + list; daily-resting-heart-rate (Daily) and
heart-rate-variability (Sample) are list only. The HRV sample emits both RMSSD (primary)
and SDNN (extra) into their own series.

heart-rate and run-vo2-max rollUp values also carry Min/Max alongside the Avg we take;
capturing those would use the same `extra` mechanism once dedicated SeriesTypes exist.
"""

from app.schemas.enums import SeriesType
from app.schemas.providers.google import DataTypeMetric, ListSpec, RollupSpec, SeriesField, TimeShape

HEART_METRICS: tuple[DataTypeMetric, ...] = (
    DataTypeMetric(
        "heart-rate",
        SeriesType.heart_rate,
        value_key="heartRate",
        rollup_spec=RollupSpec("beatsPerMinuteAvg", max_range_days=14),
        list_spec=ListSpec("beatsPerMinute", TimeShape.SAMPLE),
    ),
    DataTypeMetric(
        "run-vo2-max",
        SeriesType.vo2_max,
        value_key="runVo2Max",
        rollup_spec=RollupSpec("rateAvg"),
        list_spec=ListSpec("runVo2Max", TimeShape.SAMPLE),
    ),
    DataTypeMetric(
        "daily-resting-heart-rate",
        SeriesType.resting_heart_rate,
        value_key="dailyRestingHeartRate",
        list_spec=ListSpec("beatsPerMinute", TimeShape.DATE, is_daily_total=True),
    ),
    DataTypeMetric(
        "heart-rate-variability",
        SeriesType.heart_rate_variability_rmssd,
        value_key="heartRateVariability",
        list_spec=ListSpec(
            "rootMeanSquareOfSuccessiveDifferencesMilliseconds",
            TimeShape.SAMPLE,
            extra=(SeriesField(SeriesType.heart_rate_variability_sdnn, "standardDeviationMilliseconds"),),
        ),
    ),
)
