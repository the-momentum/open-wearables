"""Declarative mapping for data types fetched via the dataPoints *list* operation.

Some Google data types (the "Daily" summaries and a few "Sample" types) only support
``list`` / ``reconcile`` — not ``rollUp``. They're fetched with
``GET users/me/dataTypes/{dataType}/dataPoints`` and yield raw data points rather than
windowed aggregates.
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.schemas.enums import SeriesType


@dataclass(frozen=True)
class ListMetric:
    """Maps one list-only Google data type to a unified SeriesType.

    data_type:      dataType identifier in ``users/me/dataTypes/{data_type}``
                    (e.g. ``daily-resting-heart-rate``, ``daily-heart-rate-variability``).
    series_type:    the unified series this metric maps to.
    extract:        pulls a single scalar out of a data point; returns None to skip it.
                    Applied to the whole data-point dict (list values aren't a rollup union).
    is_daily_total: True for once-per-day summaries (stored as daily totals), False for
                    raw intraday samples.
    """

    data_type: str
    series_type: SeriesType
    extract: Callable[[dict[str, Any]], Decimal | None]
    is_daily_total: bool = True
