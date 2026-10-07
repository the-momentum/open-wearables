from app.schemas.enums import SeriesType
from app.services.providers.apple.coverage import HEALTH_SCORES, MEAL_FIELDS, SLEEP_FIELDS, WORKOUT_FIELDS
from app.services.providers.google_health.metrics import DAILY_ROLLUP_METRICS, DERIVED_DAILY_METRICS, METRICS

# Series from the unified metric registry, plus the civil-day totals read from dailyRollUp
# (exercise time) or derived from two of its operands (basal energy).
TIMESERIES: frozenset[SeriesType] = frozenset(
    {s for m in METRICS for s in m.series_types()}
    | {d.series_type for d in DAILY_ROLLUP_METRICS}
    | {d.series_type for d in DERIVED_DAILY_METRICS}
)

__all__ = ["HEALTH_SCORES", "MEAL_FIELDS", "SLEEP_FIELDS", "TIMESERIES", "WORKOUT_FIELDS"]
