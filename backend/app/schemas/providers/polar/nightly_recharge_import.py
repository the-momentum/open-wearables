"""Polar AccessLink v3 Nightly Recharge response schemas.

Source endpoints:
- GET /v3/users/nightly-recharge            → {"recharges": [...]}
- GET /v3/users/nightly-recharge/{date}     → either {"recharges": [entry]} or bare entry

Docs: https://www.polar.com/accesslink-api/#nightly-recharge

Persistence happens via DataPointSeries only (see
20260418[DECISION]polar_nightly_recharge_schema). Derivable averages
(heart_rate_avg, beat_to_beat_avg, heart_rate_variability_avg,
breathing_rate_avg) are deliberately not parsed.
"""

from pydantic import BaseModel, ConfigDict


class PolarNightlyRechargeEntryJSON(BaseModel):
    """Single night of Nightly Recharge data."""

    model_config = ConfigDict(extra="allow")

    polar_user: str | None = None
    date: str  # "YYYY-MM-DD"
    nightly_recharge_status: int | None = None  # 1-5 ordinal
    ans_charge: int | None = None                # -10..+10 signed
    ans_charge_status: int | None = None         # 1-5 ordinal
    hrv_samples: dict[str, float] | None = None       # "HH:MM" -> ms (int on wire, accept float for safety)
    breathing_samples: dict[str, float] | None = None # "HH:MM" -> brpm


class PolarNightlyRechargeJSON(BaseModel):
    """Wrapper shape for the list endpoint."""

    model_config = ConfigDict(extra="allow")

    recharges: list[PolarNightlyRechargeEntryJSON] = []
