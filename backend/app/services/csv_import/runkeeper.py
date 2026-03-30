"""RunKeeper CSV parser.

Parses the ``cardioActivities.csv`` file from a RunKeeper data export
and returns a list of normalised workout dicts ready for import.

CSV columns:
    Activity Id, Date, Type, Route Name, Distance (km), Duration,
    Average Pace, Average Speed (km/h), Calories Burned, Climb (m),
    Average Heart Rate (bpm), Friend's Tagged, Notes, GPX File
"""

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Any

from app.schemas.enums.workout_types import WorkoutType

RUNKEEPER_TYPE_MAP: dict[str, WorkoutType] = {
    "running": WorkoutType.RUNNING,
    "cycling": WorkoutType.CYCLING,
    "mountain biking": WorkoutType.MOUNTAIN_BIKING,
    "walking": WorkoutType.WALKING,
    "hiking": WorkoutType.HIKING,
    "downhill skiing": WorkoutType.DOWNHILL_SKIING,
    "cross-country skiing": WorkoutType.CROSS_COUNTRY_SKIING,
    "snowboarding": WorkoutType.SNOWBOARDING,
    "skating": WorkoutType.SKATING,
    "swimming": WorkoutType.SWIMMING,
    "rowing": WorkoutType.ROWING,
    "elliptical": WorkoutType.ELLIPTICAL,
    "strength training": WorkoutType.STRENGTH_TRAINING,
    "yoga": WorkoutType.YOGA,
    "other": WorkoutType.OTHER,
}


def _parse_duration(duration_str: str) -> int | None:
    """Parse RunKeeper duration string (e.g. '26:11' or '1:02:30') to seconds."""
    if not duration_str or not duration_str.strip():
        return None
    parts = duration_str.strip().split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        return None
    return None


def _parse_float(value: str) -> float | None:
    """Parse a float value, returning None for empty or invalid strings."""
    if not value or not value.strip():
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


def _parse_int(value: str) -> int | None:
    """Parse an int value, returning None for empty or invalid strings."""
    f = _parse_float(value)
    return int(f) if f is not None else None


def parse_runkeeper_csv(content: str | bytes) -> list[dict[str, Any]]:
    """Parse RunKeeper cardioActivities.csv and return normalised workout dicts.

    Each dict contains:
        external_id, start_datetime, end_datetime, workout_type,
        duration_seconds, distance_meters, calories, climb_meters,
        avg_heart_rate, avg_speed_kmh, route_name, notes, source_file
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(content))
    workouts: list[dict[str, Any]] = []

    for row in reader:
        date_str = row.get("Date", "").strip()
        if not date_str:
            continue

        start_dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        duration_seconds = _parse_duration(row.get("Duration", ""))
        end_dt = start_dt + timedelta(seconds=duration_seconds) if duration_seconds else start_dt

        activity_type = row.get("Type", "Other").strip().lower()
        workout_type = RUNKEEPER_TYPE_MAP.get(activity_type, WorkoutType.OTHER)

        distance_km = _parse_float(row.get("Distance (km)", ""))
        distance_meters = distance_km * 1000 if distance_km is not None else None

        workouts.append(
            {
                "external_id": row.get("Activity Id", "").strip() or None,
                "start_datetime": start_dt,
                "end_datetime": end_dt,
                "workout_type": workout_type,
                "duration_seconds": duration_seconds,
                "distance_meters": distance_meters,
                "calories": _parse_float(row.get("Calories Burned", "")),
                "climb_meters": _parse_float(row.get("Climb (m)", "")),
                "avg_heart_rate": _parse_int(row.get("Average Heart Rate (bpm)", "")),
                "avg_speed_kmh": _parse_float(row.get("Average Speed (km/h)", "")),
                "route_name": row.get("Route Name", "").strip() or None,
                "notes": row.get("Notes", "").strip() or None,
                "source_file": row.get("GPX File", "").strip() or None,
            }
        )

    return workouts
