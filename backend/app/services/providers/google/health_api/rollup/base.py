"""Declarative rollup-metric mapping + Google civil-time helpers.

All coupling to Google's wire format (the ``*RollupValue`` object shapes and the
``CivilDateTime`` / ``CivilTimeInterval`` types) is isolated in this module so the
247 orchestrator stays format-agnostic and corrections land in one place.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.schemas.enums import SeriesType


@dataclass(frozen=True)
class RollupMetric:
    """Maps one Google dailyRollUp data type to a unified SeriesType.

    data_type:   the dataType identifier in ``users/me/dataTypes/{data_type}`` (kebab-case
                 per Google's docs, e.g. ``steps``, ``heart-rate``, ``daily-resting-heart-rate``).
    value_key:   the union field key carrying the value in a ``DailyRollupDataPoint``
                 (camelCase, e.g. ``steps``, ``heartRate``, ``restingHeartRatePersonalRange``).
    series_type: the unified series this metric maps to.
    extract:     pulls a single scalar out of the ``*RollupValue`` object; returns None to
                 skip the data point.
    """

    data_type: str
    value_key: str
    series_type: SeriesType
    extract: Callable[[dict[str, Any]], Decimal | None]


# ---- value extraction helpers ------------------------------------------------
# NOTE: the inner field names of each *RollupValue are not in Google's published
# union doc. `first_of` tries the plausible candidates so a wrong guess degrades to
# "skipped" rather than a crash; confirm the real names against the live API.


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def first_of(*fields: str) -> Callable[[dict[str, Any]], Decimal | None]:
    """Extractor returning the first present numeric field among ``fields``.

    Looks one level deep too: a value nested as ``{field: {"value": n}}`` is unwrapped.
    """

    def _extract(value_obj: dict[str, Any]) -> Decimal | None:
        for field in fields:
            if field not in value_obj:
                continue
            raw = value_obj[field]
            if isinstance(raw, dict):
                raw = raw.get("value")
            decimal_value = _to_decimal(raw)
            if decimal_value is not None:
                return decimal_value
        return None

    return _extract


# ---- civil time (google.type.DateTime-shaped) --------------------------------
# CivilDateTime is google.type.DateTime: {year, month, day, hours, minutes, seconds,
# nanos, utcOffset|timeZone}. CivilTimeInterval carries a start/end pair. Confirm
# exact field names ("startTime"/"endTime") against the live API.


def to_civil_datetime(dt: datetime) -> dict[str, int]:
    return {
        "year": dt.year,
        "month": dt.month,
        "day": dt.day,
        "hours": dt.hour,
        "minutes": dt.minute,
        "seconds": dt.second,
    }


def civil_time_interval(start: datetime, end: datetime) -> dict[str, Any]:
    return {"startTime": to_civil_datetime(start), "endTime": to_civil_datetime(end)}


def parse_civil_datetime(obj: dict[str, Any] | None) -> datetime | None:
    if not obj:
        return None
    try:
        return datetime(
            int(obj["year"]),
            int(obj.get("month", 1)),
            int(obj.get("day", 1)),
            int(obj.get("hours", 0)),
            int(obj.get("minutes", 0)),
            int(obj.get("seconds", 0)),
            tzinfo=timezone.utc,
        )
    except (KeyError, ValueError, TypeError):
        return None
