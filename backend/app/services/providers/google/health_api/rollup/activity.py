"""Activity-family dailyRollUp metrics (steps, distance, calories, hydration)."""

from app.schemas.enums import SeriesType
from app.services.providers.google.health_api.rollup.base import RollupMetric, first_of

ACTIVITY_METRICS: tuple[RollupMetric, ...] = (
    RollupMetric("steps", "steps", SeriesType.steps, first_of("count", "total", "steps", "value")),
    RollupMetric(
        "distance",
        "distance",
        SeriesType.distance_walking_running,
        first_of("meters", "distanceMeters", "total", "value"),
    ),
    RollupMetric(
        "total-calories",
        "totalCalories",
        SeriesType.energy,
        first_of("energyKcal", "kilocalories", "calories", "kcal", "total", "value"),
    ),
    RollupMetric(
        "hydration",
        "hydrationLog",
        SeriesType.hydration,
        first_of("volumeMl", "milliliters", "total", "value"),
    ),
)
