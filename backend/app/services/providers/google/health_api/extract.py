"""Shared value/timestamp helpers for the Google Health API handlers."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any


def _to_rfc3339(dt: datetime) -> str:
    """RFC3339 UTC with a 'Z' suffix; naive datetimes are assumed UTC."""
    aware = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    return aware.strftime("%Y-%m-%dT%H:%M:%SZ")


def physical_interval(start: datetime, end: datetime) -> dict[str, str]:
    """Build a google.type.Interval; ``start`` is inclusive, ``end`` is exclusive."""
    return {"startTime": _to_rfc3339(start), "endTime": _to_rfc3339(end)}


def to_decimal(value: Any) -> Decimal | None:
    """Coerce a Google numeric value (often a string) to Decimal; None if not numeric."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def read_number(
    obj: dict[str, Any],
    field: str,
    subfield: str | None = None,
    scale: Decimal = Decimal(1),
) -> Decimal | None:
    """Read ``obj[field]`` (or ``obj[field][subfield]`` when nested), optionally unit-scaled.

    scale=0.001 converts mm to m / g to kg. Returns None if missing or not numeric.
    """
    value = obj.get(field)
    if subfield is not None:
        value = value.get(subfield) if isinstance(value, dict) else None
    number = to_decimal(value)
    return number * scale if number is not None else None


def parse_rfc3339(value: str | None) -> datetime | None:
    """Parse an RFC3339 timestamp (e.g. a data point's ``startTime``)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def parse_date(obj: dict[str, Any] | None) -> datetime | None:
    """Parse a google.type.Date ``{year, month, day}`` to midnight UTC (Daily data points)."""
    if not obj:
        return None
    try:
        return datetime(int(obj["year"]), int(obj.get("month") or 1), int(obj.get("day") or 1), tzinfo=timezone.utc)
    except (KeyError, ValueError, TypeError):
        return None
