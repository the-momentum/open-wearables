"""Pydantic schemas for Withings /v2/sleep action=getsummary responses.

API docs: https://developer.withings.com/api-reference#tag/sleep/operation/sleepv2-getsummary

Withings returns durations in SECONDS (not milliseconds) — verified against
real-world responses. Stage minutes for our EventRecordDetail are derived as
``stage_seconds // 60``.
"""

from pydantic import BaseModel, ConfigDict


class WithingsSleepSummaryDataJSON(BaseModel):
    """The ``data`` block inside a single sleep summary entry.

    Fields are listed roughly in the order the Withings docs present them.
    All numeric fields are integers (seconds, counts, bpm, etc.) except where
    noted.

    Optional / device-dependent fields (e.g. snoring, breathing disturbances,
    sleep_score) are nullable — the field is missing from the response on
    devices/plans that don't surface it. ``extra="allow"`` keeps any future
    additions from breaking deserialization.
    """

    model_config = ConfigDict(extra="allow")

    # Stage durations — SECONDS
    wakeupduration: int | None = None
    lightsleepduration: int | None = None
    deepsleepduration: int | None = None
    remsleepduration: int | None = None
    durationtosleep: int | None = None
    durationtowakeup: int | None = None

    # Wakeup events
    wakeupcount: int | None = None

    # Heart rate during sleep
    hr_average: int | None = None
    hr_min: int | None = None
    hr_max: int | None = None

    # Respiratory rate
    rr_average: int | None = None
    rr_min: int | None = None
    rr_max: int | None = None

    # Quality / scores
    sleep_score: int | None = None
    breathing_disturbances_intensity: int | None = None
    snoring: int | None = None
    snoringepisodecount: int | None = None


class WithingsSleepSummaryJSON(BaseModel):
    """One night of sleep summary (one entry in the ``series`` array)."""

    model_config = ConfigDict(extra="allow")

    id: int
    timezone: str | None = None
    model: int | None = None
    model_id: int | None = None
    hash_deviceid: str | None = None
    startdate: int  # epoch seconds, UTC
    enddate: int  # epoch seconds, UTC
    date: str | None = None  # YYYY-MM-DD in user's timezone
    data: WithingsSleepSummaryDataJSON
    created: int | None = None
    modified: int | None = None


class WithingsSleepGetsummaryResponse(BaseModel):
    """Top-level ``body`` of a sleep getsummary response (post-envelope-unwrap).

    The full Withings response is ``{"status": 0, "body": {...}}``; our
    api-client helper unwraps that envelope and the body is what gets parsed
    here.
    """

    model_config = ConfigDict(extra="allow")

    series: list[WithingsSleepSummaryJSON] = []
    more: bool | int | None = None  # 1/0 or true/false depending on endpoint
    offset: int | None = None
