# Samsung Health uses the same SDK import pipeline as Apple; coverage is identical.
from app.services.providers.apple.coverage import (  # noqa: F401
    HEALTH_SCORES,
    SLEEP_FIELDS,
    TIMESERIES,
    WORKOUT_FIELDS,
)
