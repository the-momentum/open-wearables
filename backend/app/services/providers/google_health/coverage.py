from app.schemas.enums import SeriesType
from app.services.providers.apple.coverage import HEALTH_SCORES, MEAL_FIELDS, SLEEP_FIELDS
from app.services.providers.apple.coverage import WORKOUT_FIELDS as SDK_WORKOUT_FIELDS
from app.services.providers.google_health.metrics import DAILY_ROLLUP_METRICS, DERIVED_DAILY_METRICS, METRICS

# Series from the unified metric registry, plus the civil-day totals read from dailyRollUp
# (exercise time) or derived from two of its operands (basal energy).
TIMESERIES: frozenset[SeriesType] = frozenset(
    {s for m in METRICS for s in m.series_types()}
    | {d.series_type for d in DAILY_ROLLUP_METRICS}
    | {d.series_type for d in DERIVED_DAILY_METRICS}
)

# Google Health workouts come from the REST API, which has no laps, so nothing writes `segments`.
WORKOUT_FIELDS: frozenset[str] = SDK_WORKOUT_FIELDS - {"segments"}

__all__ = ["HEALTH_SCORES", "MEAL_FIELDS", "SLEEP_FIELDS", "TIMESERIES", "WORKOUT_FIELDS"]

# ``metricsSummary.caloriesKcal``: "Total active calories burned during the workout" (Google Health workouts docs).
WORKOUT_ENERGY_SERIES = SeriesType.active_energy
