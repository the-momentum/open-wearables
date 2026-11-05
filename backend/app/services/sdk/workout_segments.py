import re
from datetime import datetime, timezone
from typing import Any

from app.schemas.providers.mobile_sdk.sync_request import Workout, WorkoutLap, WorkoutSegment

# HealthKit metadata keys, as old iOS SDK builds send them (values stringified).
_HK_STROKE_STYLE_KEY = "HKSwimmingStrokeStyle"
_HK_SWOLF_KEY = "HKSWOLFScore"

# HKSwimmingStrokeStyle raw values. Kickboard maps to the FIT `drill` stroke Garmin ingestion uses.
_HK_STROKE_STYLES: dict[int, str | None] = {
    0: None,  # unknown
    1: "mixed",
    2: "freestyle",
    3: "backstroke",
    4: "breaststroke",
    5: "butterfly",
    6: "drill",  # kickboard
}

_STROKE_NAMES: dict[str, str | None] = {
    "freestyle": "freestyle",
    "backstroke": "backstroke",
    "breaststroke": "breaststroke",
    "butterfly": "butterfly",
    "mixed": "mixed",
    "kickboard": "drill",
    "drill": "drill",
    "unknown": None,
}

_LEADING_NUMBER = re.compile(r"^\s*(-?\d+(?:\.\d+)?)")


def build_workout_segments(workout: Workout) -> list[dict[str, Any]] | None:
    """Laps and segments in the shape the FIT parser stores for Garmin; HealthKit markers are dropped."""
    items: list[tuple[str, WorkoutLap | WorkoutSegment]] = []
    for lap in workout.laps or []:
        kind = _lap_kind(lap)
        if kind is not None:
            items.append((kind, lap))
    items.extend(("split", segment) for segment in workout.segments or [])
    items.sort(key=lambda item: _as_utc(item[1].startDate))

    counters: dict[str, int] = {}
    segments: list[dict[str, Any]] = []
    for kind, item in items:
        index = counters.get(kind, 0)
        counters[kind] = index + 1
        segments.append(_build_segment(kind, index, item))
    return segments or None


def _lap_kind(lap: WorkoutLap) -> str | None:
    if lap.type == "segment":
        return "split"
    if lap.type not in (None, "lap"):
        return None
    if _stroke_style(lap) is not None or _swolf(lap) is not None:
        return "length"
    return "lap"


def _build_segment(kind: str, index: int, item: WorkoutLap | WorkoutSegment) -> dict[str, Any]:
    elapsed = (_as_utc(item.endDate) - _as_utc(item.startDate)).total_seconds()
    seg: dict[str, Any] = {
        "kind": kind,
        "index": index,
        "start_time": _iso(item.startDate),
        "elapsed_seconds": _r2(elapsed),
    }

    if isinstance(item, WorkoutSegment):
        seg["split_type"] = item.type
        seg["repetitions"] = item.repetitions
    else:
        distance = item.distanceM
        speed = _r2(distance / elapsed) if distance is not None and elapsed > 0 else None
        if kind == "length":
            seg["swim_stroke"] = _stroke_style(item)
            seg["total_strokes"] = _r2(item.strokeCount)
            seg["swolf"] = _r2(_swolf(item))
            seg["avg_speed"] = speed
            seg["length_type"] = "active"
        else:
            seg["distance_meters"] = _r2(distance)
            seg["avg_speed"] = speed
            if kind == "split":
                seg["split_type"] = "segment"

    return {k: v for k, v in seg.items() if v is not None}


def _stroke_style(lap: WorkoutLap) -> str | None:
    if lap.strokeStyle is not None:
        return _STROKE_NAMES.get(lap.strokeStyle.lower())
    raw = _metadata_number(lap, _HK_STROKE_STYLE_KEY)
    return _HK_STROKE_STYLES.get(int(raw)) if raw is not None else None


def _swolf(lap: WorkoutLap) -> float | None:
    if lap.swolf is not None:
        return lap.swolf
    return _metadata_number(lap, _HK_SWOLF_KEY)


def _metadata_number(lap: WorkoutLap, key: str) -> float | None:
    """Read a number from metadata, tolerating the `"23 count"` form an `HKQuantity` stringifies to."""
    value = (lap.metadata or {}).get(key)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str) and (match := _LEADING_NUMBER.match(value)):
        return float(match.group(1))
    return None


def _r2(v: float | None) -> float | None:
    return None if v is None else round(v, 2)


def _as_utc(v: datetime) -> datetime:
    """Treat a naive SDK timestamp as UTC, so naive and offset-aware ones compare."""
    return v if v.tzinfo else v.replace(tzinfo=timezone.utc)


def _iso(v: datetime) -> str:
    return _as_utc(v).isoformat()
