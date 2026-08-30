import re
from datetime import date, datetime, time, timezone
from typing import Annotated

from fastapi import Query
from pydantic import BeforeValidator, Field

from app.utils.exceptions import DatetimeParseError

_DATE_PARAM_DESCRIPTION = (
    "ISO 8601 datetime (e.g. `2023-11-07T05:31:56Z`) or Unix timestamp in seconds. "
    "Date-only strings (e.g. `2023-11-07`) are also accepted: start bounds normalize "
    "to midnight and end bounds to the end of the day, so date-only ranges include "
    "both boundary days."
)

_DATE_ONLY_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

DateTimeQueryParam = Annotated[
    str,
    Query(
        description=_DATE_PARAM_DESCRIPTION,
        examples=["2023-11-07T05:31:56Z", "2023-11-07"],
        json_schema_extra={"format": "date-time"},
    ),
]


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


def parse_query_end_datetime(dt_str: str) -> datetime:
    """Parse an end-of-range datetime from ISO string or Unix timestamp.

    Like parse_query_datetime, but a date-only string (e.g. `2023-11-07`) is
    normalized to the END of that day (23:59:59.999999) instead of midnight.
    Without this, a date-only end bound excludes the entire end day, and a
    single-day range (start_date == end_date) collapses to a zero-length
    window at midnight that matches nothing.

    This is a separate function rather than a boundary flag on
    parse_query_datetime because the choice is static at every call site
    (start params parse one way, end params the other): named functions keep
    call sites self-documenting, and an end bound parsed with the plain
    function is easy to spot in review.
    """
    if _DATE_ONLY_RE.fullmatch(dt_str.strip()):
        try:
            return datetime.combine(date.fromisoformat(dt_str.strip()), time.max)
        except ValueError:
            # Date-shaped but not a real calendar date (e.g. 2024-02-30).
            raise DatetimeParseError(dt_str)
    return parse_query_datetime(dt_str)


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


def to_rfc3339(dt: datetime) -> str:
    """Format a datetime as RFC3339 UTC with a 'Z' suffix; naive datetimes are assumed UTC."""
    aware = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    return aware.strftime("%Y-%m-%dT%H:%M:%SZ")


def offset_to_iso(offset_seconds: int | None) -> str | None:
    """Convert a timezone offset in seconds to ISO 8601 format (e.g. 3600 -> '+01:00')."""
    if offset_seconds is None:
        return None
    sign = "+" if offset_seconds >= 0 else "-"
    total = abs(offset_seconds)
    hours, remainder = divmod(total, 3600)
    minutes = remainder // 60
    return f"{sign}{hours:02d}:{minutes:02d}"
