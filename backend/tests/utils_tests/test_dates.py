"""Tests for date utility functions."""

from datetime import datetime, timezone

import pytest

from app.utils.dates import parse_query_datetime, parse_query_end_datetime
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


class TestParseQueryEndDatetime:
    """Test suite for parse_query_end_datetime."""

    def test_date_only_normalizes_to_end_of_day(self) -> None:
        result = parse_query_end_datetime("2024-01-01")
        assert result == datetime(2024, 1, 1, 23, 59, 59, 999999)

    def test_single_day_range_covers_the_whole_day(self) -> None:
        start = parse_query_datetime("2024-01-01")
        end = parse_query_end_datetime("2024-01-01")
        midday = datetime(2024, 1, 1, 12, 0, 0)
        assert start <= midday <= end

    def test_full_iso_datetime_passes_through(self) -> None:
        result = parse_query_end_datetime("2024-01-01T05:31:56+00:00")
        assert result == datetime(2024, 1, 1, 5, 31, 56, tzinfo=timezone.utc)

    def test_unix_timestamp_passes_through(self) -> None:
        result = parse_query_end_datetime("1704067200")
        assert result == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_invalid_format_raises_error(self) -> None:
        with pytest.raises(DatetimeParseError):
            parse_query_end_datetime("invalid")
