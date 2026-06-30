"""Activity-family metrics (steps, distance, calories, hydration).

rollUp value fields confirmed against the live API. Distance is reported in millimeters
(scaled to meters). list value fields are inferred (only used at RAW granularity).
"""

from decimal import Decimal

from app.schemas.enums import SeriesType
from app.schemas.providers.google import DataTypeMetric, ListSpec, RollupSpec, TimeShape

_MM_TO_M = Decimal("0.001")

ACTIVITY_METRICS: tuple[DataTypeMetric, ...] = (
    DataTypeMetric(
        "steps",
        SeriesType.steps,
        rollup_spec=RollupSpec("steps", "countSum"),
        list_spec=ListSpec("count", TimeShape.INTERVAL),
    ),
    DataTypeMetric(
        "distance",
        SeriesType.distance_walking_running,
        rollup_spec=RollupSpec("distance", "millimetersSum", scale=_MM_TO_M),
        list_spec=ListSpec("millimeters", TimeShape.INTERVAL, scale=_MM_TO_M),
    ),
    DataTypeMetric(
        "total-calories",
        SeriesType.energy,
        rollup_spec=RollupSpec("totalCalories", "kcalSum", max_range_days=14),  # rollUp-only
    ),
    DataTypeMetric(
        "hydration-log",
        SeriesType.hydration,
        rollup_spec=RollupSpec("hydrationLog", "amountConsumed", subfield="millilitersSum"),
        list_spec=ListSpec("amountConsumed", TimeShape.INTERVAL, subfield="milliliters"),
    ),
)
