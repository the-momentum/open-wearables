from typing import Literal

from pydantic import BaseModel, Field


class NightlyRechargeJSON(BaseModel):
    polar_user: str | None = None
    date: str | None = None
    heart_rate_avg: int | None = None
    beat_to_beat_avg: int | None = None
    heart_rate_variability_avg: int | None = None  # rmssd, ms
    breathing_rate_avg: float | None = None
    # very poor (1) – poor (2) – compromised (3) – OK (4) – good (5) – very good (6)
    nightly_recharge_status: Literal[1, 2, 3, 4, 5, 6] | None = None
    # scale from -10 to 10, 0 is usual level
    ans_charge: float | None = Field(default=None, ge=-10, le=10)
    # (1) - below usual (2) - usual (3) - above usual (4) - much above usual (5)
    ans_charge_status: Literal[1, 2, 3, 4, 5] | None = None
    hrv_samples: dict[str, int] | None = None
    breathing_samples: dict[str, float] | None = None


class NightlyRechargeResponseJSON(BaseModel):
    recharges: list[NightlyRechargeJSON] | None = None
