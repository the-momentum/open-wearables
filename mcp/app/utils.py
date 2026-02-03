"""Common utility functions for MCP tools."""

from datetime import datetime


def normalize_datetime(dt_str: str | None) -> str | None:
    """Normalize datetime string to ISO 8601 format."""
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.isoformat()
    except (ValueError, AttributeError):
        return dt_str
