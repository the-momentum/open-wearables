"""Body-measurement metrics (weight, body fat, core temp, glucose).

rollUp value fields confirmed against the live API. Weight is reported in grams (scaled
to kg). core-body-temperature also carries Min/Max alongside the Avg we take (future
multi-series). list value fields are inferred (only used at RAW granularity).
"""

from decimal import Decimal

from app.schemas.enums import SeriesType
from app.schemas.providers.google import DataTypeMetric, ListSpec, RollupSpec, TimeShape

_G_TO_KG = Decimal("0.001")

BODY_METRICS: tuple[DataTypeMetric, ...] = (
    DataTypeMetric(
        "weight",
        SeriesType.weight,
        rollup_spec=RollupSpec("weight", "weightGramsAvg", scale=_G_TO_KG),
        list_spec=ListSpec("weightGrams", TimeShape.SAMPLE, scale=_G_TO_KG),
    ),
    DataTypeMetric(
        "body-fat",
        SeriesType.body_fat_percentage,
        rollup_spec=RollupSpec("bodyFat", "bodyFatPercentageAvg"),
        list_spec=ListSpec("percentage", TimeShape.SAMPLE),
    ),
    DataTypeMetric(
        "core-body-temperature",
        SeriesType.body_temperature,
        rollup_spec=RollupSpec("coreBodyTemperature", "temperatureCelsiusAvg"),
        list_spec=ListSpec("temperatureCelsius", TimeShape.SAMPLE),
    ),
    DataTypeMetric(
        "blood-glucose",
        SeriesType.blood_glucose,
        rollup_spec=RollupSpec("bloodGlucose", "bloodGlucoseMilligramsPerDeciliterAvg"),
        list_spec=ListSpec("bloodGlucoseMilligramsPerDeciliter", TimeShape.SAMPLE),
    ),
)
