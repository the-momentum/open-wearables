"""Body-measurement metrics (weight, body fat, core temp, glucose).

Value fields confirmed against the live API. Weight is reported in grams (scaled to kg).
core-body-temperature also carries Min/Max alongside the Avg we take (future multi-series).
"""

from decimal import Decimal

from app.schemas.enums import SeriesType
from app.schemas.providers.google import DataTypeMetric, ListSpec, RollupSpec, TimeShape

_G_TO_KG = Decimal("0.001")

BODY_METRICS: tuple[DataTypeMetric, ...] = (
    DataTypeMetric(
        "weight",
        SeriesType.weight,
        value_key="weight",
        rollup_spec=RollupSpec("weightGramsAvg", scale=_G_TO_KG),
        list_spec=ListSpec("weightGrams", TimeShape.SAMPLE, scale=_G_TO_KG),
    ),
    DataTypeMetric(
        "body-fat",
        SeriesType.body_fat_percentage,
        value_key="bodyFat",
        rollup_spec=RollupSpec("bodyFatPercentageAvg"),
        list_spec=ListSpec("percentage", TimeShape.SAMPLE),
    ),
    DataTypeMetric(
        "core-body-temperature",
        SeriesType.body_temperature,
        value_key="coreBodyTemperature",
        rollup_spec=RollupSpec("temperatureCelsiusAvg"),
        list_spec=ListSpec("celsius", TimeShape.SAMPLE),
    ),
    DataTypeMetric(
        "blood-glucose",
        SeriesType.blood_glucose,
        value_key="bloodGlucose",
        rollup_spec=RollupSpec("bloodGlucoseMilligramsPerDeciliterAvg"),
        list_spec=ListSpec("bloodGlucoseMilligramsPerDeciliter", TimeShape.SAMPLE),
    ),
)
