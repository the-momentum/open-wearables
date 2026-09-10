"""Activity-family metrics (steps, distance, calories, hydration).

Value fields confirmed against the live API. Distance is reported in millimeters
(scaled to meters). Energy is split active/basal; total-calories mixes the two into one
sum and has no list form, so it is not ingested.
"""

from decimal import Decimal

from app.schemas.enums import SeriesType
from app.schemas.providers.google import DataTypeMetric, ListSpec, RollupSpec, TimeShape

_MM_TO_M = Decimal("0.001")

ACTIVITY_METRICS: tuple[DataTypeMetric, ...] = (
    DataTypeMetric(
        "steps",
        SeriesType.steps,
        value_key="steps",
        rollup_spec=RollupSpec("countSum"),
        list_spec=ListSpec("count", TimeShape.INTERVAL),
    ),
    DataTypeMetric(
        "distance",
        SeriesType.distance_walking_running,
        value_key="distance",
        rollup_spec=RollupSpec("millimetersSum", scale=_MM_TO_M),
        list_spec=ListSpec("millimeters", TimeShape.INTERVAL, scale=_MM_TO_M),
    ),
    DataTypeMetric(
        "active-energy-burned",
        SeriesType.energy,
        value_key="activeEnergyBurned",
        rollup_spec=RollupSpec("kcalSum"),
        list_spec=ListSpec("kcal", TimeShape.INTERVAL),
    ),
    DataTypeMetric(
        "basal-energy-burned",
        SeriesType.basal_energy,
        value_key="basalEnergyBurned",
        list_spec=ListSpec("kcal", TimeShape.INTERVAL),
    ),
    DataTypeMetric(
        "hydration-log",
        SeriesType.hydration,
        value_key="hydrationLog",
        rollup_spec=RollupSpec("amountConsumed", subfield="millilitersSum"),
        list_spec=ListSpec("amountConsumed", TimeShape.INTERVAL, subfield="milliliters", session_interval=True),
    ),
)
