"""Body-measurement dailyRollUp metrics (weight, body fat, core temp, glucose)."""

from app.schemas.enums import SeriesType
from app.services.providers.google.health_api.extract import first_of
from app.services.providers.google.health_api.rollup.base import RollupMetric

# Averaged metrics presumably aggregate with Avg (see heart.py note); confirm field
# names against a live sample per value type.
_AVG = ("average", "avg", "mean", "value")

BODY_METRICS: tuple[RollupMetric, ...] = (
    RollupMetric("weight", "weight", SeriesType.weight, first_of("kilogramAvg", "kilogramsAvg", *_AVG, "kilograms")),
    RollupMetric(
        "body-fat",
        "bodyFat",
        SeriesType.body_fat_percentage,
        first_of("percentageAvg", *_AVG, "percentage"),
    ),
    RollupMetric(
        "core-body-temperature",
        "coreBodyTemperature",
        SeriesType.body_temperature,
        first_of("celsiusAvg", *_AVG, "celsius", "degreesCelsius"),
    ),
    RollupMetric(
        "blood-glucose",
        "bloodGlucose",
        SeriesType.blood_glucose,
        first_of("mgdlAvg", *_AVG, "mgdl", "millimolesPerLiter"),
    ),
)
