"""Activity-family metrics (steps, distance, calories, hydration).

Value fields confirmed against the live API. Distance is reported in millimeters
(scaled to meters). total-calories mixes active with basal and has no list form, so it is
not ingested here; basal is derived from it in metrics/derived.py.
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
        SeriesType.active_energy,
        value_key="activeEnergyBurned",
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
