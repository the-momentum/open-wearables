"""Pydantic schemas for Withings /v2/measure action=getworkouts responses.

API docs: https://developer.withings.com/api-reference#tag/measure/operation/measurev2-getworkouts

Returned payload uses minute-level epoch timestamps for ``startdate`` /
``enddate``. Optional ``data`` fields depend on the workout category and the
device's sensor coverage — most fields are nullable.
"""

from pydantic import BaseModel, ConfigDict


class WithingsWorkoutDataJSON(BaseModel):
    """The ``data`` block inside a single workout entry.

    All numeric fields are integers or floats; the API returns whatever the
    device captured. Heart-rate zones are seconds-spent-in-zone.
    """

    model_config = ConfigDict(extra="allow")

    # Energy / output
    calories: float | int | None = None
    intensity: int | None = None

    # Distance / elevation (meters)
    distance: float | int | None = None
    manual_distance: float | int | None = None
    elevation: float | int | None = None
    elevation_climbed: float | int | None = None  # alt name in some payloads

    # Heart rate
    hr_average: int | None = None
    hr_min: int | None = None
    hr_max: int | None = None
    hr_zone_0: int | None = None
    hr_zone_1: int | None = None
    hr_zone_2: int | None = None
    hr_zone_3: int | None = None

    # Activity
    steps: int | None = None
    spo2_average: int | None = None
    pause_duration: int | None = None
    algo_pause_duration: int | None = None

    # Pool-specific
    pool_laps: int | None = None
    strokes: int | None = None
    pool_length: int | None = None


class WithingsWorkoutJSON(BaseModel):
    """One workout entry in the ``series`` array."""

    model_config = ConfigDict(extra="allow")

    id: int | None = None  # not always present in older payloads
    category: int  # see constants/workout_types/withings.py for the map
    timezone: str | None = None
    model: int | None = None
    model_id: int | None = None
    attrib: int | None = None
    startdate: int  # epoch seconds, UTC
    enddate: int  # epoch seconds, UTC
    date: str | None = None  # YYYY-MM-DD in user's timezone
    modified: int | None = None
    data: WithingsWorkoutDataJSON | None = None


class WithingsWorkoutGetworkoutsResponse(BaseModel):
    """Top-level body of a getworkouts response (post-envelope-unwrap)."""

    model_config = ConfigDict(extra="allow")

    series: list[WithingsWorkoutJSON] = []
    more: bool | int | None = None
    offset: int | None = None
