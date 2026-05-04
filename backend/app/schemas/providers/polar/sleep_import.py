"""Polar AccessLink v3 Sleep Plus Stages response schemas.

Source endpoints:
- GET /v3/users/sleep           — list of up to 28 recent nights.
- GET /v3/users/sleep/{date}    — single night, identical element shape.

Docs: https://www.polar.com/accesslink-api/#sleep

Notes:
- `hypnogram` is a dict of ``"HH:MM"`` transition-start → integer stage code.
  The value is the stage entered at that wall-clock time, running until the
  next key or until ``sleep_end_time`` for the last interval.
- `heart_rate_samples` in the sleep payload is ``{"HH:MM": bpm_int}`` —
  different shape from the continuous-HR endpoint which uses a list.
- Polar tends to return snake_case for v3 but other endpoints in the same
  surface use hyphenated keys; tolerate both via ``populate_by_name=True`` +
  ``extra="allow"`` so upstream key drift doesn't break parsing.
"""

from pydantic import BaseModel, ConfigDict, Field


class PolarSleepJSON(BaseModel):
    """Single night entry from ``/v3/users/sleep`` or ``/v3/users/sleep/{date}``."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    polar_user: str | None = None
    date: str | None = None

    sleep_start_time: str | None = Field(default=None, validation_alias="sleep-start-time")
    sleep_end_time: str | None = Field(default=None, validation_alias="sleep-end-time")
    device_id: str | None = Field(default=None, validation_alias="device-id")

    # Durations in seconds
    light_sleep: int | None = None
    deep_sleep: int | None = None
    rem_sleep: int | None = None
    unrecognized_sleep_stage: int | None = None
    total_interruption_duration: int | None = None
    short_interruption_duration: int | None = None
    long_interruption_duration: int | None = None
    sleep_goal: int | None = None

    # Scores and classifications (documented ranges: sleep_score 1-100, sleep_charge/sleep_rating 1-5)
    sleep_score: int | None = None
    sleep_charge: int | None = None
    sleep_rating: int | None = None
    sleep_cycles: int | None = None

    continuity: float | None = None
    continuity_class: int | None = None
    group_duration_score: float | None = None
    group_solidity_score: float | None = None
    group_regeneration_score: float | None = None

    # Time-series inside the night
    hypnogram: dict[str, int] | None = None
    heart_rate_samples: dict[str, int] | None = None


class PolarSleepNightsJSON(BaseModel):
    """Wrapper response shape for ``GET /v3/users/sleep``."""

    model_config = ConfigDict(extra="allow")

    nights: list[PolarSleepJSON] = Field(default_factory=list)
