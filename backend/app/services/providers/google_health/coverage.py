from app.schemas.enums import SeriesType
from app.services.providers.apple.coverage import HEALTH_SCORES, SLEEP_FIELDS, WORKOUT_FIELDS
from app.services.providers.google_health.metrics import DERIVED_DAILY_METRICS, METRICS

# Series from the unified metric registry, plus the daily totals derived from two
# dailyRollUp operands (basal energy).
TIMESERIES: frozenset[SeriesType] = frozenset(
    {s for m in METRICS for s in m.series_types()} | {d.series_type for d in DERIVED_DAILY_METRICS}
)

__all__ = ["HEALTH_SCORES", "SLEEP_FIELDS", "TIMESERIES", "WORKOUT_FIELDS"]
