"""Vitals metrics (respiratory rate, oxygen saturation, sleep skin temperature) — list-only types.

daily-respiratory-rate and daily-sleep-temperature-derivations are Daily types (date-stamped);
oxygen-saturation is a Sample type (instantaneous). None supports rollUp. Units already match
(brpm, percent, Celsius).

daily-sleep-temperature-derivations carries the mean nightly skin temperature
(``nightlyTemperatureCelsius``) plus a 30-day baseline median and stddev; only the nightly
mean is a measurement, so it maps to ``skin_temperature`` and the deviation from baseline is
left to consumers (the baseline fields have no unified series).
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
        "daily-sleep-temperature-derivations",
        SeriesType.skin_temperature,
        value_key="dailySleepTemperatureDerivations",
        list_spec=ListSpec("nightlyTemperatureCelsius", TimeShape.DATE, is_daily_total=True),
    ),
)
