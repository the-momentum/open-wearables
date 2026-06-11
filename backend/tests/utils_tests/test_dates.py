"""Tests for date utility functions."""

from datetime import datetime, timedelta, timezone

import pytest

from app.utils.dates import iso_zone_offset, parse_query_datetime
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


class TestIsoZoneOffset:
    def test_positive_offset_from_iso_string(self) -> None:
        assert iso_zone_offset("2026-05-05T02:56:00+03:00") == "+03:00"

    def test_z_suffix_yields_utc(self) -> None:
        assert iso_zone_offset("2026-05-05T02:56:00Z") == "+00:00"

    def test_naive_string_returns_none(self) -> None:
        assert iso_zone_offset("2026-05-05T02:56:00") is None

    def test_prefers_first_tz_aware_candidate(self) -> None:
        assert iso_zone_offset(None, "2026-05-05T02:56:00", "2026-05-05T02:56:00+02:00") == "+02:00"

    def test_datetime_candidate(self) -> None:
        aware = datetime(2026, 5, 5, 2, 56, tzinfo=timezone(timedelta(hours=3)))
        assert iso_zone_offset(aware) == "+03:00"
