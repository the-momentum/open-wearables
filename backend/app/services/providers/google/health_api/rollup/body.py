"""Body-measurement dailyRollUp metrics (weight, body fat, core temp, glucose)."""

from app.schemas.enums import SeriesType
from app.services.providers.google.health_api.rollup.base import RollupMetric, first_of

_AVG = ("average", "avg", "mean", "value")

BODY_METRICS: tuple[RollupMetric, ...] = (
    RollupMetric("weight", "weight", SeriesType.weight, first_of(*_AVG, "kilograms")),
    RollupMetric("body-fat", "bodyFat", SeriesType.body_fat_percentage, first_of(*_AVG, "percentage")),
    RollupMetric(
        "core-body-temperature",
        "coreBodyTemperature",
        SeriesType.body_temperature,
        first_of(*_AVG, "celsius", "degreesCelsius"),
    ),
    RollupMetric(
        "blood-glucose",
        "bloodGlucose",
        SeriesType.blood_glucose,
        first_of(*_AVG, "mgdl", "millimolesPerLiter"),
    ),
)
