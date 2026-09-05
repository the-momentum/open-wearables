"""Model the Withings payload fields required by ingestion.

Spec-documented ranges are declared as constraints rather than comments, so a
payload that violates one is rejected by the per-record guard in the ingestion
path instead of being normalized into a wrong value.
"""

# Aliased: three models carry a payload field named ``date``, which would shadow
# the type in its own annotation (the value binds before the annotation is read).
from datetime import date as date_type

from pydantic import BaseModel, Field


class WithingsMeasure(BaseModel):
    """``measure_object``: the real value is ``value × 10^unit``."""

    value: int  # unbounded: some meastypes are legitimately negative
    type: int = Field(ge=0)
    unit: int
    position: int | None = None


class WithingsMeasureGroup(BaseModel):
    """``measuregrp_object`` — one timestamped group of measures."""

    date: int
    # Payloads may place the timezone on the group or only on the response body.
    timezone: str | None = None
    measures: list[WithingsMeasure] = []
    grpid: int | None = None
    # attrib 0/8 = device-captured & unambiguous, 2/4 = manual entry (see spec table).
    attrib: int | None = None
    category: int | None = None
    deviceid: str | None = None
    model: str | None = None


class WithingsActivity(BaseModel):
    """``activity_object`` — a daily aggregate from ``getactivity``."""

    # Local calendar day the totals are aggregated over.
    date: date_type
    timezone: str | None = None
    # deviceid identifies the capturing device but may be absent on valid rows;
    # the echo filter is brand == 18, not deviceid absence.
    deviceid: str | None = None
    # Origin signals: brand 1 = Withings, 18 = external/echo (e.g. Health Connect).
    # is_tracker = captured by Withings hardware.
    brand: int | None = None
    is_tracker: bool | None = None
    steps: int | None = Field(default=None, ge=0)
    distance: float | None = Field(default=None, ge=0)
    calories: float | None = Field(default=None, ge=0)  # active kcal
    totalcalories: float | None = Field(default=None, ge=0)  # active + passive kcal


class WithingsSleepData(BaseModel):
    """``sleep_summary_object.data`` — the fields we request via ``data_fields``.

    Durations are nullable: the spec nulls light/deep/REM for nights that come
    from an external source.
    """

    total_timeinbed: int | None = Field(default=None, ge=0)
    total_sleep_time: int | None = Field(default=None, ge=0)
    asleepduration: int | None = Field(default=None, ge=0)
    deepsleepduration: int | None = Field(default=None, ge=0)
    lightsleepduration: int | None = Field(default=None, ge=0)
    remsleepduration: int | None = Field(default=None, ge=0)
    wakeupduration: int | None = Field(default=None, ge=0)
    # Ratio of total sleep time over time in bed.
    sleep_efficiency: float | None = Field(default=None, ge=0, le=1)


class WithingsSleepSummary(BaseModel):
    """``sleep_summary_object`` — one night/session from ``getsummary``."""

    startdate: int
    enddate: int
    id: int | None = None
    date: date_type | None = None
    timezone: str | None = None
    # model 16 = tracker, 32 = Sleep Monitor (sleep summaries carry no deviceid).
    model: int | None = None
    model_id: int | None = None
    data: WithingsSleepData = Field(default_factory=WithingsSleepData)


class WithingsWorkoutData(BaseModel):
    """``workout_object.data`` — the fields we request via ``data_fields``."""

    calories: float | None = Field(default=None, ge=0)
    steps: int | None = Field(default=None, ge=0)
    distance: float | None = Field(default=None, ge=0)
    elevation: float | None = None  # unbounded: descent and below-sea-level are valid
    hr_average: int | None = Field(default=None, ge=0)
    hr_min: int | None = Field(default=None, ge=0)
    hr_max: int | None = Field(default=None, ge=0)


class WithingsWorkout(BaseModel):
    """``workout_object`` — one session from ``getworkouts``."""

    category: int = Field(ge=0)
    startdate: int
    enddate: int
    id: int | None = None
    attrib: int | None = None
    date: date_type | None = None
    timezone: str | None = None
    # Workouts retain rows without deviceid and do not apply the activity echo filter.
    deviceid: str | None = None
    data: WithingsWorkoutData = Field(default_factory=WithingsWorkoutData)
