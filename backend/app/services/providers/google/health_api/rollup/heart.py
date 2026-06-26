"""Heart-family dailyRollUp metrics (heart rate, resting HR, HRV, VO2 max).

Google reports HRV as RMSSD (not SDNN), so heartRateVariabilityPersonalRange maps
to SeriesType.heart_rate_variability_rmssd.
"""

from app.schemas.enums import SeriesType
from app.services.providers.google.health_api.rollup.base import RollupMetric, first_of

_AVG = ("average", "avg", "mean", "value")

HEART_METRICS: tuple[RollupMetric, ...] = (
    RollupMetric("heart-rate", "heartRate", SeriesType.heart_rate, first_of(*_AVG, "bpm", "beatsPerMinute")),
    RollupMetric(
        "daily-resting-heart-rate",
        "restingHeartRatePersonalRange",
        SeriesType.resting_heart_rate,
        first_of(*_AVG, "bpm", "restingHeartRate"),
    ),
    RollupMetric(
        "daily-heart-rate-variability",
        "heartRateVariabilityPersonalRange",
        SeriesType.heart_rate_variability_rmssd,
        first_of(*_AVG, "rmssd", "milliseconds"),
    ),
    RollupMetric("run-vo2-max", "runVo2Max", SeriesType.vo2_max, first_of("value", *_AVG, "vo2Max")),
)
