"""Declarative rollUp-metric mapping + the physical Interval request helper.

Value/timestamp coercion lives in ``health_api.extract`` (shared with ``listed``);
this module holds only what's specific to the dataPoints:rollUp operation.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.schemas.enums import SeriesType


@dataclass(frozen=True)
class RollupMetric:
    """Maps one Google ``dataPoints:rollUp`` data type to a unified SeriesType.

    data_type:      the dataType identifier in ``users/me/dataTypes/{data_type}`` (kebab-case
                    per Google's docs, e.g. ``steps``, ``heart-rate``, ``daily-resting-heart-rate``).
    value_key:      the union field key carrying the value in a ``RollupDataPoint``
                    (camelCase, e.g. ``steps``, ``heartRate``, ``restingHeartRatePersonalRange``).
    series_type:    the unified series this metric maps to.
    extract:        pulls a single scalar out of the ``*RollupValue`` object; returns None to
                    skip the data point.
    max_range_days: rollUp caps a single request's range per data type — 14 days for
                    heart-rate / total-calories / active-minutes / calories-in-heart-rate-zone,
                    90 days for everything else. The fetcher chunks longer ranges to fit.
    """

    data_type: str
    value_key: str
    series_type: SeriesType
    extract: Callable[[dict[str, Any]], Decimal | None]
    max_range_days: int = 90


# ---- physical time -----------------------------------------------------------
# rollUp uses google.type.Interval (physical time): a closed-open range of RFC3339
# timestamps {"startTime": ..., "endTime": ...}.


def _to_rfc3339(dt: datetime) -> str:
    """RFC3339 UTC with a 'Z' suffix; naive datetimes are assumed UTC."""
    aware = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    return aware.strftime("%Y-%m-%dT%H:%M:%SZ")


def physical_interval(start: datetime, end: datetime) -> dict[str, str]:
    """Build an Interval; ``start`` is inclusive, ``end`` is exclusive."""
    return {"startTime": _to_rfc3339(start), "endTime": _to_rfc3339(end)}
