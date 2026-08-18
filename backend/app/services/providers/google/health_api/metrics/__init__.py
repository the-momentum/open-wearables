"""Unified registry of Google Health API data types — the single source of truth for
what the 24/7 handler emits. Add a metric by appending one ``DataTypeMetric`` to the
relevant family module. Spec types live in ``app.schemas.providers.google``.
"""

from app.schemas.providers.google import DataTypeMetric
from app.services.providers.google.health_api.metrics.activity import ACTIVITY_METRICS
from app.services.providers.google.health_api.metrics.body import BODY_METRICS
from app.services.providers.google.health_api.metrics.heart import HEART_METRICS
from app.services.providers.google.health_api.metrics.vitals import VITALS_METRICS

METRICS: tuple[DataTypeMetric, ...] = (*ACTIVITY_METRICS, *HEART_METRICS, *BODY_METRICS, *VITALS_METRICS)

__all__ = ["METRICS"]
