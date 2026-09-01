"""Tests for app.utils.config_utils helpers."""

from datetime import timedelta

import pytest

from app.utils.config_utils import format_duration, parse_duration


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2d", timedelta(days=2)),
        ("20h", timedelta(hours=20)),
        ("90m", timedelta(minutes=90)),
        ("1d12h", timedelta(days=1, hours=12)),
        ("1d12h30m", timedelta(days=1, hours=12, minutes=30)),
        (" 2D ", timedelta(days=2)),  # trimmed + case-insensitive
    ],
)
def test_parse_duration_valid(value: str, expected: timedelta) -> None:
    assert parse_duration(value) == expected


@pytest.mark.parametrize("value", ["", "abc", "2", "d", "2x", "2days", "-2d", "1.5h"])
def test_parse_duration_invalid_raises(value: str) -> None:
    with pytest.raises(ValueError, match="Invalid duration"):
        parse_duration(value)


@pytest.mark.parametrize(
    ("td", "expected"),
    [
        (timedelta(days=2), "2d"),
        (timedelta(hours=20), "20h"),
        (timedelta(days=1, hours=12), "1d12h"),
        (timedelta(minutes=90), "1h30m"),
        (timedelta(0), "0m"),
    ],
)
def test_format_duration(td: timedelta, expected: str) -> None:
    assert format_duration(td) == expected
