"""Default configuration values for health score algorithms."""

from typing import Self

from pydantic import BaseModel, Field, model_validator

# HRV RECOVERY SCORE


class RecoveryScoreConfig(BaseModel):
    lookback_days: int = Field(default=7, ge=1)
    min_days_required: int = Field(default=5, ge=2)
    min_rr_samples: int = Field(default=20, ge=2)

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        if self.min_days_required > self.lookback_days:
            msg = "min_days_required must be <= lookback_days"
            raise ValueError(msg)
        return self


recovery_config = RecoveryScoreConfig()
