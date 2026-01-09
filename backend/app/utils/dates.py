from datetime import datetime, timezone

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
