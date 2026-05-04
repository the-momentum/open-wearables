"""Polar AccessLink v3 Continuous Heart Rate response schemas.

Source endpoints:
- GET /v3/users/continuous-heart-rate/{date}
- GET /v3/users/continuous-heart-rate?from=YYYY-MM-DD&to=YYYY-MM-DD

Docs: https://www.polar.com/accesslink-api/#continuous-heart-rate

Samples are 5-minute averages (some denser intervals). ``sample_time`` is
wall-clock ``HH:MM:SS`` relative to ``date`` (no timezone on the wire — we
combine as UTC-naive, matching the policy Phase 1 uses for daily activity).
"""

from pydantic import BaseModel, ConfigDict


class PolarContinuousHRSample(BaseModel):
    """Single continuous-HR sample: bpm + wall-clock time-of-day."""

    model_config = ConfigDict(extra="allow")

    heart_rate: int
    sample_time: str  # "HH:MM:SS"


class PolarContinuousHRJSON(BaseModel):
    """Response shape for per-date Continuous HR endpoint."""

    model_config = ConfigDict(extra="allow")

    polar_user: str | None = None
    date: str  # "YYYY-MM-DD"
    heart_rate_samples: list[PolarContinuousHRSample] = []
