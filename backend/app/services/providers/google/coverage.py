from app.constants.series_types.sdk.metric_types import ANDROID_METRIC_TYPE_TO_SERIES_TYPE
from app.constants.series_types.sdk.workout_statistics import WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE
from app.schemas.enums import SeriesType
from app.services.providers.apple.coverage import HEALTH_SCORES, SLEEP_FIELDS, WORKOUT_FIELDS
from app.services.providers.google.health_api.rollup import ROLLUP_METRICS

# Google data arrives through two paths under one provider identity:
#   - Health Connect SDK: Android/HC metric types (RMSSD, not SDNN)
#   - Health API cloud rollups: daily-summary series derived from the rollup registry
ROLLUP_SERIES: frozenset[SeriesType] = frozenset(m.series_type for m in ROLLUP_METRICS)

TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        *ANDROID_METRIC_TYPE_TO_SERIES_TYPE.values(),
        *WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE.values(),
        *ROLLUP_SERIES,
    }
)

__all__ = ["HEALTH_SCORES", "ROLLUP_SERIES", "SLEEP_FIELDS", "TIMESERIES", "WORKOUT_FIELDS"]
