"""Registry of Google data types fetched via the dataPoints *list* operation —
the list-only counterpart to ``rollup``. Add a metric by appending one ``ListMetric``
to the relevant family module.
"""

from app.services.providers.google.health_api.listed.base import ListMetric
from app.services.providers.google.health_api.listed.heart import HEART_METRICS

LIST_METRICS: tuple[ListMetric, ...] = (*HEART_METRICS,)

__all__ = ["LIST_METRICS", "ListMetric"]
