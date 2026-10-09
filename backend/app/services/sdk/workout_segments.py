"""Moving time from a Health Connect exercise session's segments.

A Health Connect session spans from start to stop, pauses included, so its
``endDate - startDate`` is elapsed time, not the time the athlete was moving. The
session's segments say which parts were which. The Android SDK sends each one as
``{"startDate", "endDate", "type"}``, where ``type`` is a name for the segment kinds
it knows ("running", "rest", ...) and ``other_<n>`` for the rest; a pause is
``other_39`` (``ExerciseSegment.EXERCISE_SEGMENT_TYPE_PAUSE``).
"""

from datetime import datetime
from typing import Any

# Segment types during which the athlete is not moving.
_IDLE_TYPES = frozenset({"rest", "pause", "other_39"})


def _seconds(segment: dict[str, Any]) -> float | None:
    try:
        start = datetime.fromisoformat(str(segment["startDate"]))
        end = datetime.fromisoformat(str(segment["endDate"]))
        # TypeError here: one timestamp has an offset and the other does not.
        seconds = (end - start).total_seconds()
    except (KeyError, TypeError, ValueError):
        return None
    return seconds if seconds > 0 else None


def health_connect_moving_time(segments: list[dict[str, Any]] | None, elapsed_seconds: int) -> int | None:
    """Seconds spent moving, or None when the segments do not say.

    ``elapsed_seconds`` is the session's ``endDate - startDate``: pauses are
    subtracted from it, so it must not be a duration statistic that may already
    leave them out.

    Active segments are summed when there are any: an app that marks only the running
    part of a session (Fitbit does) leaves the rest of it unsegmented, and that part is
    not movement either. A session segmented only into pauses and rests is the other
    way round, so those are subtracted from the elapsed time instead.
    """
    if not segments:
        return None

    active = idle = 0.0
    for segment in segments:
        kind = segment.get("type")
        seconds = _seconds(segment)
        # A segment without a type says nothing about movement, so it is skipped
        # rather than counted as active.
        if seconds is None or not isinstance(kind, str) or not kind.strip():
            continue
        if kind.strip().lower() in _IDLE_TYPES:
            idle += seconds
        else:
            active += seconds

    if active:
        moving = active
    elif idle:
        moving = elapsed_seconds - idle
    else:
        return None
    return max(0, min(int(round(moving)), elapsed_seconds))
