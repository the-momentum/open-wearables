"""Shared value/timestamp extraction helpers for the Google Health API handlers.

Used by both the ``rollup`` (dataPoints:rollUp) and ``listed`` (dataPoints list)
registries so the coercion logic lives in one place.
"""

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


def to_decimal(value: Any) -> Decimal | None:
    """Coerce a Google numeric value (often a string) to Decimal; None if not numeric."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def first_of(*fields: str) -> Callable[[dict[str, Any]], Decimal | None]:
    """Return an extractor that yields the first present numeric field among ``fields``.

    Looks one level deep too: a value nested as ``{field: {"value": n}}`` is unwrapped.
    NOTE: candidate field names are partly inferred from Google's docs; a wrong guess
    degrades to "skipped" rather than crashing — confirm against a live response.
    """

    def _extract(obj: dict[str, Any]) -> Decimal | None:
        for field in fields:
            if field not in obj:
                continue
            raw = obj[field]
            if isinstance(raw, dict):
                raw = raw.get("value")
            decimal_value = to_decimal(raw)
            if decimal_value is not None:
                return decimal_value
        return None

    return _extract


def parse_rfc3339(value: str | None) -> datetime | None:
    """Parse an RFC3339 timestamp (e.g. a data point's ``startTime``)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
