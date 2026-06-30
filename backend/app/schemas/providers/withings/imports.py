"""Withings payload models (spec source: ``measure_object``, ``measuregrp_object``,
``activity_object``, ``sleep_summary_object``, ``workout_object``).

The spec marks no field as required (responses are ``data_fields``-driven), so
required-ness here reflects our ingestion invariants: a record missing these is
unusable and is skipped by the per-record tolerance in the data handlers. Field
types follow live payloads over the spec where they disagree (e.g. workout
distance/calories arrive as floats, not integers).
"""

from pydantic import BaseModel, Field


class WithingsMeasure(BaseModel):
    """``measure_object``: the real value is ``value × 10^unit``."""

    value: int
    type: int
    unit: int
    position: int | None = None


class WithingsMeasureGroup(BaseModel):
    """``measuregrp_object`` — one timestamped group of measures."""

    # UNIX timestamp at which the measures were taken.
    date: int
    measures: list[WithingsMeasure] = []
    grpid: int | None = None
    # attrib 0/8 = device-captured & unambiguous, 2/4 = manual entry (see spec table).
    attrib: int | None = None
    category: int | None = None
    deviceid: str | None = None
    model: str | None = None


class WithingsActivity(BaseModel):
    """``activity_object`` — a daily aggregate from ``getactivity``."""

    # Date of the aggregated data, ``YYYY-MM-DD``.
    date: str
    timezone: str | None = None
    # null/absent deviceid = foreign-aggregated day (echo filter).
    deviceid: str | None = None
    # Origin signals kept for future filtering: brand 1 = Withings, 18 = external;
    # is_tracker = captured by Withings hardware.
    brand: int | None = None
    is_tracker: bool | None = None
    steps: int | None = None
    distance: float | None = None
    calories: float | None = None  # active kcal
    totalcalories: float | None = None  # active + passive kcal
    soft: int | None = None
    moderate: int | None = None
    intense: int | None = None
    hr_average: int | None = None
    hr_min: int | None = None
    hr_max: int | None = None


class WithingsSleepData(BaseModel):
    """``sleep_summary_object.data`` — the fields we request via ``data_fields``.

    Durations are nullable: the spec nulls light/deep/REM for nights that come
    from an external source.
    """

    deepsleepduration: int | None = None
    lightsleepduration: int | None = None
    remsleepduration: int | None = None
    wakeupduration: int | None = None
    # Ratio of total sleep time over time in bed, 0.0–1.0 per spec.
    sleep_efficiency: float | None = None
    sleep_score: int | None = None
    hr_average: int | None = None
    rr_average: int | None = None


class WithingsSleepSummary(BaseModel):
    """``sleep_summary_object`` — one night/session from ``getsummary``."""

    startdate: int
    enddate: int
    id: int | None = None
    date: str | None = None
    timezone: str | None = None
    # model 16 = tracker, 32 = Sleep Monitor (sleep summaries carry no deviceid).
    model: int | None = None
    model_id: int | None = None
    data: WithingsSleepData = Field(default_factory=WithingsSleepData)


class WithingsWorkoutData(BaseModel):
    """``workout_object.data`` — the fields we request via ``data_fields``."""

    calories: float | None = None
    steps: int | None = None
    distance: float | None = None
    elevation: float | None = None
    hr_average: int | None = None
    hr_min: int | None = None
    hr_max: int | None = None


class WithingsWorkout(BaseModel):
    """``workout_object`` — one session from ``getworkouts``."""

    category: int
    startdate: int
    enddate: int
    id: int | None = None
    attrib: int | None = None
    date: str | None = None
    timezone: str | None = None
    # null/absent deviceid = imported from a foreign source (echo-filter signal).
    deviceid: str | None = None
    data: WithingsWorkoutData = Field(default_factory=WithingsWorkoutData)
