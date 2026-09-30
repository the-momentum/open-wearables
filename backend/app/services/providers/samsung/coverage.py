from app.constants.series_types.sdk.metric_types import SAMSUNG_METRIC_TYPE_TO_SERIES_TYPE
from app.constants.series_types.sdk.workout_statistics import WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE
from app.schemas.enums import SeriesType
from app.services.providers.apple.coverage import HEALTH_SCORES, SLEEP_FIELDS, WORKOUT_FIELDS

# Samsung Health Data SDK emits Android metric types, minus resting HR and HRV (not exposed by Samsung).
TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        *SAMSUNG_METRIC_TYPE_TO_SERIES_TYPE.values(),
        *WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE.values(),
    }
)

__all__ = ["HEALTH_SCORES", "SLEEP_FIELDS", "TIMESERIES", "WORKOUT_FIELDS"]
