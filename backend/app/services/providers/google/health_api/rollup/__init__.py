"""Registry of Google dailyRollUp metrics — the single source of truth for what
the Health API 24/7 handler emits. Add a metric by appending one ``RollupMetric``
to the relevant family module; the orchestrator and coverage derive from this tuple.
"""

from app.services.providers.google.health_api.rollup.activity import ACTIVITY_METRICS
from app.services.providers.google.health_api.rollup.base import RollupMetric, physical_interval
from app.services.providers.google.health_api.rollup.body import BODY_METRICS
from app.services.providers.google.health_api.rollup.heart import HEART_METRICS

ROLLUP_METRICS: tuple[RollupMetric, ...] = (*ACTIVITY_METRICS, *HEART_METRICS, *BODY_METRICS)

__all__ = [
    "ROLLUP_METRICS",
    "RollupMetric",
    "physical_interval",
]
