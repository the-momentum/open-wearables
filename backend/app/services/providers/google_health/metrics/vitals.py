"""Vitals metrics (respiratory rate, oxygen saturation) — list-only types.

daily-respiratory-rate and daily-oxygen-saturation are Daily types (date-stamped);
oxygen-saturation is a Sample type (instantaneous). None support rollUp. Units already
match (brpm, percent). SpO2 is registered in both shapes because a source populates one
or the other — HealthKit-origin accounts only carry the daily average.
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
    DataTypeMetric(
        "daily-oxygen-saturation",
        SeriesType.oxygen_saturation,
        value_key="dailyOxygenSaturation",
        list_spec=ListSpec("averagePercentage", TimeShape.DATE, is_daily_total=True),
    ),
)
