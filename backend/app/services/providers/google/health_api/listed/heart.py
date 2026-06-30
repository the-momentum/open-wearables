"""Heart-family list-only metrics: daily resting HR and daily HRV (RMSSD).

Both are Google "Daily" record types (list/reconcile only). Google reports HRV as
RMSSD (not SDNN), so daily-heart-rate-variability maps to heart_rate_variability_rmssd.
"""

from app.schemas.enums import SeriesType
from app.services.providers.google.health_api.extract import first_of
from app.services.providers.google.health_api.listed.base import ListMetric

# Field names within a list data point are not yet confirmed against a live response;
# first_of() searches these candidates and skips (rather than crashes) on a miss.
HEART_METRICS: tuple[ListMetric, ...] = (
    ListMetric(
        "daily-resting-heart-rate",
        SeriesType.resting_heart_rate,
        first_of("bpm", "restingHeartRate", "value", "average"),
    ),
    ListMetric(
        "daily-heart-rate-variability",
        SeriesType.heart_rate_variability_rmssd,
        first_of("rmssd", "rmssdMilliseconds", "hrv", "milliseconds", "value"),
    ),
)
