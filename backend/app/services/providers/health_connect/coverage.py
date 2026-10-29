from app.constants.series_types.sdk.metric_types import ANDROID_METRIC_TYPE_TO_SERIES_TYPE
from app.constants.series_types.sdk.workout_samples import WORKOUT_ROUTE_SERIES
from app.constants.series_types.sdk.workout_statistics import WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE
from app.schemas.enums import SeriesType
from app.services.providers.apple.coverage import HEALTH_SCORES, MEAL_FIELDS, SLEEP_FIELDS, WORKOUT_FIELDS

# Health Connect emits Android/HC metric types (RMSSD, not SDNN).
TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        *ANDROID_METRIC_TYPE_TO_SERIES_TYPE.values(),
        *WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE.values(),
        *WORKOUT_ROUTE_SERIES,  # workouts[].route, gated by settings.ingest_workout_samples
    }
)

__all__ = ["HEALTH_SCORES", "MEAL_FIELDS", "SLEEP_FIELDS", "TIMESERIES", "WORKOUT_FIELDS"]
