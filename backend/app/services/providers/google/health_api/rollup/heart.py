"""Heart-family rollUp metrics (heart rate, VO2 max).

Resting HR and HRV are Google "Daily" record types that only support list/reconcile
(no rollUp), so they live in the ``listed`` registry, not here.
"""

from app.schemas.enums import SeriesType
from app.services.providers.google.health_api.extract import first_of
from app.services.providers.google.health_api.rollup.base import RollupMetric

# Averaged metrics presumably aggregate with Avg (mirroring the confirmed `countSum`
# for steps); exact field names per value type still need a live sample to pin down.
_AVG = ("average", "avg", "mean", "value")

HEART_METRICS: tuple[RollupMetric, ...] = (
    RollupMetric(
        "heart-rate",
        "heartRate",
        SeriesType.heart_rate,
        first_of("bpmAvg", "averageBpm", *_AVG, "bpm"),
        max_range_days=14,  # rollUp caps heart-rate at 14 days/request
    ),
    RollupMetric(
        "run-vo2-max",
        "runVo2Max",
        SeriesType.vo2_max,
        first_of("vo2MaxAvg", "valueAvg", *_AVG, "vo2Max"),
    ),
)
