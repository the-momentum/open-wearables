from datetime import datetime, timezone


def parse_query_datetime(dt_str: str) -> datetime:
    """Parse datetime from ISO string or Unix timestamp (seconds)."""
    try:
        # Try parsing as Unix timestamp
        timestamp = float(dt_str)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except ValueError:
        # Fallback to ISO format
        return datetime.fromisoformat(dt_str)
