from app.constants.series_types.sdk.metric_types import ANDROID_METRIC_TYPE_TO_SERIES_TYPE
from app.constants.series_types.sdk.workout_statistics import WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE
from app.schemas.enums import SeriesType
from app.services.providers.apple.coverage import HEALTH_SCORES, SLEEP_FIELDS, WORKOUT_FIELDS
from app.services.providers.google.health_api.metrics import METRICS

# Google data arrives through two paths under one provider identity:
#   - Health Connect SDK: Android/HC metric types (RMSSD, not SDNN)
#   - Health API cloud: series from the unified rollUp + list metric registry
HEALTH_API_SERIES: frozenset[SeriesType] = frozenset(m.series_type for m in METRICS)

TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        *ANDROID_METRIC_TYPE_TO_SERIES_TYPE.values(),
        *WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE.values(),
        *HEALTH_API_SERIES,
    }
)

__all__ = ["HEALTH_API_SERIES", "HEALTH_SCORES", "SLEEP_FIELDS", "TIMESERIES", "WORKOUT_FIELDS"]
