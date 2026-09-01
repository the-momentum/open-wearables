"""Tests for date utility functions."""

from datetime import datetime, timedelta, timezone

import pytest

from app.utils.dates import align_tz_awareness, parse_query_datetime
from app.utils.exceptions import DatetimeParseError


class TestParseQueryDatetime:
    """Test suite for parse_query_datetime."""

    def test_parse_unix_timestamp(self) -> None:
        result = parse_query_datetime("1704067200")
        assert result == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_parse_iso_format(self) -> None:
        result = parse_query_datetime("2024-01-01T00:00:00+00:00")
        assert result == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_invalid_format_raises_error(self) -> None:
        with pytest.raises(DatetimeParseError) as exc_info:
            parse_query_datetime("invalid")
        assert "Invalid datetime format" in exc_info.value.detail


class TestAlignTzAwareness:
    """Test suite for align_tz_awareness."""

    def test_naive_start_borrows_end_offset(self) -> None:
        tz = timezone(timedelta(hours=2))
        start, end = align_tz_awareness(datetime(2026, 6, 9, 3, 3), datetime(2026, 6, 9, 10, 35, tzinfo=tz))
        assert start == datetime(2026, 6, 9, 3, 3, tzinfo=tz)
        assert end == datetime(2026, 6, 9, 10, 35, tzinfo=tz)

    def test_naive_end_borrows_start_offset(self) -> None:
        tz = timezone(timedelta(hours=-5))
        start, end = align_tz_awareness(datetime(2026, 6, 9, 3, 3, tzinfo=tz), datetime(2026, 6, 9, 10, 35))
        assert start == datetime(2026, 6, 9, 3, 3, tzinfo=tz)
        assert end == datetime(2026, 6, 9, 10, 35, tzinfo=tz)

    def test_leaves_matching_pairs_untouched(self) -> None:
        naive = (datetime(2026, 6, 9, 3, 3), datetime(2026, 6, 9, 10, 35))
        assert align_tz_awareness(*naive) == naive

        aware = (
            datetime(2026, 6, 9, 3, 3, tzinfo=timezone.utc),
            datetime(2026, 6, 9, 10, 35, tzinfo=timezone(timedelta(hours=2))),
        )
        assert align_tz_awareness(*aware) == aware

    def test_passes_through_when_either_edge_is_missing(self) -> None:
        dt = datetime(2026, 6, 9, 3, 3)
        assert align_tz_awareness(dt, None) == (dt, None)
        assert align_tz_awareness(None, dt) == (None, dt)
