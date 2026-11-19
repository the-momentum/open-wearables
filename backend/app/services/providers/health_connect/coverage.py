from app.constants.series_types.sdk.metric_types import ANDROID_METRIC_TYPE_TO_SERIES_TYPE
from app.constants.series_types.sdk.reproductive_health import HEALTH_CONNECT_REPRODUCTIVE_HEALTH_TYPES
from app.constants.series_types.sdk.workout_samples import WORKOUT_ROUTE_SERIES
from app.constants.series_types.sdk.workout_statistics import WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE
from app.schemas.enums import SeriesType
from app.services.providers.apple.coverage import HEALTH_SCORES, MEAL_FIELDS, SLEEP_FIELDS
from app.services.providers.apple.coverage import WORKOUT_FIELDS as APPLE_WORKOUT_FIELDS

# Health Connect emits Android/HC metric types (RMSSD, not SDNN).
TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        *ANDROID_METRIC_TYPE_TO_SERIES_TYPE.values(),
        *WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE.values(),
        *WORKOUT_ROUTE_SERIES,  # workouts[].route, gated by settings.ingest_workout_samples
    }
)

# Health Connect sends pedaling cadence as `meanCadence`, which lands in the cadence series, not the detail field
WORKOUT_FIELDS: frozenset[str] = APPLE_WORKOUT_FIELDS - {"average_cadence"}

# Samsung Health has no matching types, so only Health Connect declares these.
REPRODUCTIVE_HEALTH_TYPES = HEALTH_CONNECT_REPRODUCTIVE_HEALTH_TYPES

__all__ = ["HEALTH_SCORES", "MEAL_FIELDS", "REPRODUCTIVE_HEALTH_TYPES", "SLEEP_FIELDS", "TIMESERIES", "WORKOUT_FIELDS"]
