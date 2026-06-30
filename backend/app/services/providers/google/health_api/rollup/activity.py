"""Activity-family dailyRollUp metrics (steps, distance, calories, hydration)."""

from app.schemas.enums import SeriesType
from app.services.providers.google.health_api.extract import first_of
from app.services.providers.google.health_api.rollup.base import RollupMetric

# Rollup values use a `<unit><AggFn>` field, e.g. steps -> {"countSum": "1382"} (confirmed).
# Cumulative metrics aggregate with Sum; values arrive as numeric strings (first_of coerces).
ACTIVITY_METRICS: tuple[RollupMetric, ...] = (
    RollupMetric("steps", "steps", SeriesType.steps, first_of("countSum", "count")),
    RollupMetric(
        "distance",
        "distance",
        SeriesType.distance_walking_running,
        first_of("distanceSum", "meterSum", "metersSum", "meters"),
    ),
    RollupMetric(
        "total-calories",
        "totalCalories",
        SeriesType.energy,
        first_of("energySum", "calorieSum", "kcalSum", "energyKcal"),
        max_range_days=14,  # rollUp caps total-calories at 14 days/request
    ),
    RollupMetric(
        "hydration-log",
        "hydrationLog",
        SeriesType.hydration,
        first_of("volumeSum", "volumeMlSum", "milliliterSum", "volumeMl"),
    ),
)
