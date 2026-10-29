from app.constants.series_types.sdk.metric_types import ANDROID_METRIC_TYPE_TO_SERIES_TYPE
from app.constants.series_types.sdk.workout_statistics import WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE
from app.schemas.enums import SeriesType
from app.services.providers.apple.coverage import HEALTH_SCORES, MEAL_FIELDS, SLEEP_FIELDS
from app.services.providers.apple.coverage import WORKOUT_FIELDS as APPLE_WORKOUT_FIELDS

# Health Connect emits Android/HC metric types (RMSSD, not SDNN).
TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        *ANDROID_METRIC_TYPE_TO_SERIES_TYPE.values(),
        *WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE.values(),
    }
)

# Health Connect sends pedaling cadence as `meanCadence`, which lands in the cadence series, not the detail field
WORKOUT_FIELDS: frozenset[str] = APPLE_WORKOUT_FIELDS - {"average_cadence"}

__all__ = ["HEALTH_SCORES", "MEAL_FIELDS", "SLEEP_FIELDS", "TIMESERIES", "WORKOUT_FIELDS"]
