from datetime import datetime, timezone
from typing import Annotated

from pydantic import BeforeValidator, Field

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


def parse_webhook_data_timestamp(data_timestamp: str | None) -> datetime:
    """Parse a webhook data_timestamp to a UTC datetime.

    Tries ISO 8601 parsing; falls back to ``datetime.now(timezone.utc)``
    when the value is ``None`` or unparseable.
    """
    if data_timestamp:
        try:
            dt = datetime.fromisoformat(data_timestamp.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, AttributeError):
            pass
    return datetime.now(timezone.utc)


def offset_to_iso(offset_seconds: int | None) -> str | None:
    """Convert a timezone offset in seconds to ISO 8601 format (e.g. 3600 -> '+01:00')."""
    if offset_seconds is None:
        return None
    sign = "+" if offset_seconds >= 0 else "-"
    total = abs(offset_seconds)
    hours, remainder = divmod(total, 3600)
    minutes = remainder // 60
    return f"{sign}{hours:02d}:{minutes:02d}"


def _normalize_zone_offset(v: str | None) -> str | None:
    if v == "Z":
        return "+00:00"
    return v


ZoneOffset = Annotated[
    str | None,
    Field(
        None,
        description="Timezone offset in the format '+01:00' or '-05:30'",
        pattern=r"^[+-]\d{2}:\d{2}$",
        examples=["+01:00", "-05:30"],
        max_length=10,
    ),
    BeforeValidator(_normalize_zone_offset),
]
