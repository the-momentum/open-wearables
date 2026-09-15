"""Vitals metrics (respiratory rate, oxygen saturation) — list-only types.

daily-respiratory-rate is a Daily type (date-stamped); oxygen-saturation is a Sample
type (instantaneous). Neither supports rollUp. Units already match (brpm, percent).
"""

from app.schemas.enums import SeriesType
from app.schemas.providers.google import DataTypeMetric, ListSpec, TimeShape

VITALS_METRICS: tuple[DataTypeMetric, ...] = (
    DataTypeMetric(
        "daily-respiratory-rate",
        SeriesType.respiratory_rate,
        value_key="dailyRespiratoryRate",
        list_spec=ListSpec("breathsPerMinute", TimeShape.DATE, is_daily_total=True),
    ),
    DataTypeMetric(
        "oxygen-saturation",
        SeriesType.oxygen_saturation,
        value_key="oxygenSaturation",
        list_spec=ListSpec("percentage", TimeShape.SAMPLE),
    ),
)
