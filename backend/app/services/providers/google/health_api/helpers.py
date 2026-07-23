"""Shared value/timestamp helpers for the Google Health API handlers."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.utils.conversion import to_decimal
from app.utils.dates import offset_to_iso, to_rfc3339

GOOGLE_HEALTH_API_SOURCE = "google_health_api"


def physical_interval(start: datetime, end: datetime) -> dict[str, str]:
    """Build a google.type.Interval; ``start`` is inclusive, ``end`` is exclusive."""
    return {"startTime": to_rfc3339(start), "endTime": to_rfc3339(end)}


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


def extract_source(data_source: Any) -> tuple[str, str | None]:
    """Derive (source_name, device_model) from a list data point's dataSource.

    device shapes vary: {displayName} (Fitbit), {manufacturer, formFactor} (Health
    Connect), or empty/absent. device_model falls back displayName -> manufacturer
    formFactor -> platform; source_name is the platform.
    """
    if not isinstance(data_source, dict):
        return "Google Health", None
    device = data_source.get("device") or {}
    platform = data_source.get("platform")
    form_factor = device.get("formFactor")
    device_model = (
        device.get("displayName")
        or " ".join(p for p in (device.get("manufacturer"), form_factor.lower() if form_factor else None) if p)
        or platform
        or None
    )
    return platform or "Google Health", device_model


def parse_duration_seconds(value: str | None) -> Decimal | None:
    """Parse a Google Duration string (seconds ending in 's', e.g. ``1830s``) to seconds."""
    if not value:
        return None
    return to_decimal(value[:-1] if value.endswith("s") else value)


def zone_offset_from(utc_offset: str | None) -> str | None:
    """Convert a Google UTC-offset Duration ('7200s') to an ISO offset ('+02:00')."""
    seconds = parse_duration_seconds(utc_offset)
    return offset_to_iso(int(seconds)) if seconds is not None else None


def parse_rfc3339(value: str | None) -> datetime | None:
    """Parse an RFC3339 timestamp (e.g. a data point's ``startTime``)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def parse_interval(interval: dict[str, Any] | None) -> tuple[datetime | None, datetime | None]:
    """Parse an interval's ``startTime``/``endTime`` (RFC3339) into datetimes."""
    interval = interval or {}
    return parse_rfc3339(interval.get("startTime")), parse_rfc3339(interval.get("endTime"))


def parse_date(obj: dict[str, Any] | None) -> datetime | None:
    """Parse a google.type.Date ``{year, month, day}`` to midnight UTC (Daily data points)."""
    if not obj:
        return None
    try:
        return datetime(int(obj["year"]), int(obj.get("month") or 1), int(obj.get("day") or 1), tzinfo=timezone.utc)
    except (KeyError, ValueError, TypeError):
        return None
