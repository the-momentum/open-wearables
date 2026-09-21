from app.schemas.enums import SeriesType
from app.services.providers.apple.coverage import HEALTH_SCORES, MEAL_FIELDS, SLEEP_FIELDS, WORKOUT_FIELDS
from app.services.providers.google_health.metrics import DERIVED_DAILY_METRICS, METRICS
from app.services.providers.google_health.nutrition import NUTRITION_SERIES_TYPES

# Series from the unified metric registry, the daily totals derived from two dailyRollUp
# operands (basal energy), and the nutrients the nutrition-log handler emits.
TIMESERIES: frozenset[SeriesType] = frozenset(
    {s for m in METRICS for s in m.series_types()}
    | {d.series_type for d in DERIVED_DAILY_METRICS}
    | NUTRITION_SERIES_TYPES
)

__all__ = ["HEALTH_SCORES", "MEAL_FIELDS", "SLEEP_FIELDS", "TIMESERIES", "WORKOUT_FIELDS"]
