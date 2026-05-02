"""Pydantic schemas for Withings /measure action=getmeas responses.

API docs: https://developer.withings.com/api-reference#tag/measure/operation/measure-getmeas

Withings encodes physical-quantity values as ``value * 10**unit`` to avoid
floats — e.g. ``{"value": 7400, "unit": -2}`` means 74.00. Conversion happens
in the consumer (``data_247.py``), not in the schema.

Measure type integers we currently support (matched to SeriesType in
constants/workout_types/withings.py would be wrong — actual map lives in
data_247.py to keep import graph small):

  - 1   weight                  (kg)         → SeriesType.weight
  - 4   height                  (m → cm)     → SeriesType.height
  - 5   fat_free_mass / lean    (kg)         → SeriesType.lean_body_mass
  - 6   fat_ratio               (% × 1000)   → SeriesType.body_fat_percentage
  - 8   fat_mass_weight         (kg)         → SeriesType.body_fat_mass
  - 9   diastolic_bp            (mmHg)       → SeriesType.blood_pressure_diastolic
  - 10  systolic_bp             (mmHg)       → SeriesType.blood_pressure_systolic
  - 11  heart_pulse             (bpm)        → SeriesType.resting_heart_rate
  - 76  muscle_mass             (kg)         → SeriesType.skeletal_muscle_mass
  - 77  hydration               (kg)         → SeriesType.hydration
  - 88  bone_mass               (kg)         → DROPPED (no SeriesType match)
"""

from pydantic import BaseModel, ConfigDict


class WithingsMeasureValueJSON(BaseModel):
    """A single measurement within a measure group.

    ``value * 10**unit`` is the actual physical value in the unit dictated by
    ``type``. ``algo`` and ``fm`` describe the computation algorithm and are
    not currently consumed.
    """

    model_config = ConfigDict(extra="allow")

    value: int
    type: int
    unit: int
    algo: int | None = None
    fm: int | None = None


class WithingsMeasureGroupJSON(BaseModel):
    """One measurement session (a single weighing, e.g.)."""

    model_config = ConfigDict(extra="allow")

    grpid: int
    attrib: int | None = None  # provenance code (0/1 = the user, 2 = imported, 4-12 = various)
    date: int  # epoch seconds, UTC — when the measurement happened
    created: int | None = None
    modified: int | None = None
    category: int | None = None  # 1 = real, 2 = user objective
    deviceid: str | None = None
    hash_deviceid: str | None = None
    measures: list[WithingsMeasureValueJSON]
    modelid: int | None = None
    model: str | None = None
    comment: str | None = None
    timezone: str | None = None


class WithingsMeasureGetmeasResponse(BaseModel):
    """Top-level body of a getmeas response (post-envelope-unwrap)."""

    model_config = ConfigDict(extra="allow")

    updatetime: int | None = None
    timezone: str | None = None
    measuregrps: list[WithingsMeasureGroupJSON] = []
    more: bool | int | None = None
    offset: int | None = None
