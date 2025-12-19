"""Utilities for cursor-based pagination."""

import base64
import binascii
from datetime import datetime
from typing import Generic, Protocol, TypeVar
from uuid import UUID

from app.utils.dates import parse_query_datetime
from app.utils.exceptions import InvalidCursorError


class CursorItem(Protocol):
    """Protocol for items that can be used with cursor pagination."""

    recorded_at: datetime
    id: UUID


T = TypeVar("T", bound=CursorItem)


def encode_cursor(timestamp: datetime, item_id: UUID, direction: str = "next") -> str:
    """Encode a cursor from timestamp and ID.

    Args:
        timestamp: The timestamp of the item
        item_id: The UUID of the item
        direction: Either 'next' or 'prev' to indicate pagination direction

    Returns:
        Base64 encoded cursor, prefixed with 'prev_' if direction is 'prev'
    """
    cursor_str = f"{timestamp.isoformat()}|{item_id}"
    encoded = base64.urlsafe_b64encode(cursor_str.encode("utf-8")).decode("utf-8")

    if direction == "prev":
        return f"prev_{encoded}"
    return encoded


def decode_cursor(cursor: str) -> tuple[datetime, UUID, str]:
    """Decode a cursor to timestamp, ID, and direction.

    Args:
        cursor: The cursor string to decode

    Returns:
        Tuple of (timestamp, item_id, direction) where direction is 'next' or 'prev'

    Raises:
        InvalidCursorError: If cursor format is invalid
    """
    try:
        # Check for direction prefix
        direction = "next"
        if cursor.startswith("prev_"):
            direction = "prev"
            cursor = cursor[5:]  # Remove "prev_" prefix

        decoded_cursor = base64.urlsafe_b64decode(cursor).decode("utf-8")
        cursor_ts_str, cursor_id_str = decoded_cursor.split("|")
        cursor_ts = parse_query_datetime(cursor_ts_str)
        cursor_id = UUID(cursor_id_str)
        return cursor_ts, cursor_id, direction
    except (ValueError, TypeError, binascii.Error):
        raise InvalidCursorError(cursor=cursor)


class PaginationResult(Generic[T]):
    """Result of pagination processing with cursors."""

    def __init__(
        self,
        data: list[T],
        next_cursor: str | None,
        previous_cursor: str | None,
        has_more: bool,
    ):
        self.data = data
        self.next_cursor = next_cursor
        self.previous_cursor = previous_cursor
        self.has_more = has_more


def process_paginated_results(
    results: list[T],
    limit: int,
    has_cursor: bool,
) -> PaginationResult[T]:
    """
    Process paginated results and generate cursors.

    Args:
        results: List of items from repository (may include extra items for pagination)
        limit: Requested page size
        has_cursor: Whether a cursor was used in the query

    Returns:
        PaginationResult with data, cursors, and has_more flag
    """
    previous_element: T | None = None

    # If we used cursor and got extra previous element, extract it
    # Repository prepends previous item when cursor is used
    # Check if we got limit + 2 items (prev + limit + 1 for has_more check)
    if has_cursor and len(results) > limit + 1:
        previous_element = results[0]
        results = results[1:]

    has_more = len(results) > limit
    next_cursor: str | None = None
    previous_cursor: str | None = None

    if has_more:
        # Trim to requested limit
        results = results[:limit]

    # Generate cursors if we have data
    if results:
        last_item = results[-1]

        # Next cursor: points to last item, only if there's more data
        if has_more:
            next_cursor = encode_cursor(last_item.recorded_at, last_item.id)

        # Previous cursor: points to element BEFORE first item
        if previous_element:
            previous_cursor = encode_cursor(previous_element.recorded_at, previous_element.id)

    return PaginationResult(
        data=results,
        next_cursor=next_cursor,
        previous_cursor=previous_cursor,
        has_more=has_more,
    )
