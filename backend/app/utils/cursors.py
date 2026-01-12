"""Cursor utilities for keyset pagination."""

import base64
import binascii
from datetime import datetime
from uuid import UUID

from app.utils.exceptions import InvalidCursorError


def encode_cursor(timestamp: datetime, item_id: UUID, direction: str = "next") -> str:
    """Encode a cursor for pagination.

    Args:
        timestamp: The timestamp of the item
        item_id: The UUID of the item
        direction: Either "next" or "prev" to indicate direction

    Returns:
        Base64 encoded cursor string with direction prefix
    """
    cursor_str = f"{timestamp.isoformat()}|{item_id}"
    encoded = base64.urlsafe_b64encode(cursor_str.encode()).decode()

    if direction == "prev":
        return f"prev_{encoded}"
    return encoded


def decode_cursor(cursor: str) -> tuple[datetime, UUID, str]:
    """Decode a cursor for pagination.

    Args:
        cursor: The cursor string to decode

    Returns:
        Tuple of (timestamp, item_id, direction)
        where direction is "next" or "prev"

    Raises:
        InvalidCursorError: If cursor format is invalid
    """
    try:
        # Check for direction prefix
        direction = "next"
        if cursor.startswith("prev_"):
            direction = "prev"
            cursor = cursor[5:]  # Remove "prev_" prefix

        # Decode base64
        decoded_cursor = base64.urlsafe_b64decode(cursor).decode("utf-8")
        cursor_ts_str, cursor_id_str = decoded_cursor.split("|")

        # Parse timestamp and UUID
        from app.utils.dates import parse_query_datetime

        cursor_ts = parse_query_datetime(cursor_ts_str)
        cursor_id = UUID(cursor_id_str)

        return cursor_ts, cursor_id, direction
    except (ValueError, TypeError, binascii.Error) as e:
        raise InvalidCursorError(cursor=cursor) from e
