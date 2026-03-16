from datetime import datetime, timezone
from typing import Literal

from app.utils.exceptions import DatetimeParseError


def parse_query_datetime(dt_str: str) -> datetime:
    """Parse datetime from ISO string or Unix timestamp (seconds).

    Raises:
        DatetimeParseError: If the string is not a valid ISO 8601 datetime or Unix timestamp.
    """
    try:
        timestamp = float(dt_str)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except ValueError:
        pass

    try:
        return datetime.fromisoformat(dt_str)
    except ValueError:
        raise DatetimeParseError(dt_str)


def parse_iso_datetime(dt_str: str | None) -> datetime | None:
    """Parse ISO 8601 datetime string, handling trailing Z notation.

    Converts "Z" suffix to "+00:00" timezone offset before parsing.
    Returns None if the string is None or invalid.

    Args:
        dt_str: ISO 8601 datetime string (e.g., "2024-01-15T08:00:00Z")

    Returns:
        Parsed datetime with timezone or None if parsing fails
    """
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def parse_datetime_or_default(
    value: datetime | str | None,
    fallback: datetime,
) -> datetime:
    """Parse a datetime-or-string argument, falling back to default.

    Args:
        value: Datetime object, ISO string, or None
        fallback: Default datetime to use if value is None or invalid

    Returns:
        Parsed datetime or fallback
    """
    if value is None:
        return fallback
    if isinstance(value, str):
        return parse_iso_datetime(value) or fallback
    return value


def offset_to_iso(offset: int | None, unit: Literal["seconds", "minutes"] = "seconds") -> str | None:
    """Convert a numeric timezone offset to ISO 8601 format (e.g. '+01:00', '-05:30').

    Args:
        offset: Timezone offset as an integer (or None).
        unit: Whether the offset is in 'seconds' (Garmin) or 'minutes' (Polar).

    Returns:
        ISO 8601 offset string like '+01:00', or None if offset is None.
    """
    if offset is None:
        return None
    total_seconds = offset if unit == "seconds" else offset * 60
    sign = "+" if total_seconds >= 0 else "-"
    abs_seconds = abs(total_seconds)
    hours, remainder = divmod(abs_seconds, 3600)
    minutes = remainder // 60
    return f"{sign}{hours:02d}:{minutes:02d}"
