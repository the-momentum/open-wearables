from app.constants.series_types.sdk.metric_types import (
    ANDROID_METRIC_TYPE_TO_SERIES_TYPE,
    APPLE_METRIC_TYPE_TO_SERIES_TYPE,
)
from app.constants.series_types.sdk.workout_statistics import WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE
from app.schemas.enums import SeriesType
from app.services.providers.apple.coverage import HEALTH_SCORES, MEAL_FIELDS, SLEEP_FIELDS, WORKOUT_FIELDS

# Coverage describes the native ingestion interface, not the sensors of a particular band.
# Both HRV identifiers are accepted; the exporter must establish SDNN versus RMSSD.
METRIC_TYPES = {**ANDROID_METRIC_TYPE_TO_SERIES_TYPE, **APPLE_METRIC_TYPE_TO_SERIES_TYPE}
TIMESERIES: frozenset[SeriesType] = frozenset({*METRIC_TYPES.values(), *WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE.values()})

__all__ = ["HEALTH_SCORES", "MEAL_FIELDS", "METRIC_TYPES", "SLEEP_FIELDS", "TIMESERIES", "WORKOUT_FIELDS"]
