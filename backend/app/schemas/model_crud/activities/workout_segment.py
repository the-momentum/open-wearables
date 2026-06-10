from pydantic import BaseModel

from app.constants.workout_segments import SegmentKind


class WorkoutSegment(BaseModel):
    """A sub-activity breakdown (lap, split or pool length) stored inside the JSONB column."""

    kind: SegmentKind
    index: int
    distance_meters: float | None = None
    duration_seconds: int | None = None
    moving_time_seconds: int | None = None
    average_speed: float | None = None
    average_heartrate: float | None = None
    max_heartrate: int | None = None
    average_cadence: float | None = None
    average_watts: float | None = None
    total_elevation_gain: float | None = None
