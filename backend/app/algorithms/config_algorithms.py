"""Default configuration values for health score algorithms."""

from typing import Self

from pydantic import BaseModel, Field, model_validator

# SLEEP SCORE


class SleepScoreConfig(BaseModel):
    # --- SCORE MASTER WEIGHTS ---
    # must add up to 1.0 - weighted average
    duration_impact: float = 0.40
    stages_impact: float = 0.20
    consistency_impact: float = 0.20
    interruptions_impact: float = 0.20

    @model_validator(mode="after")
    def validate_impacts_sum_to_one(self) -> Self:
        total = self.duration_impact + self.stages_impact + self.consistency_impact + self.interruptions_impact
        if abs(total - 1.0) > 1e-9:
            msg = f"Pillar impacts must sum to 1.0, got {total}"
            raise ValueError(msg)
        return self

    # SLEEP DURATION
    optimal_min_hours: float = 7.0
    optimal_max_hours: float = 9.0
    undersleep_k: float = 1.5
    undersleep_midpoint: float = 5.0
    oversleep_k: float = 0.8
    oversleep_midpoint: float = 11.0

    # SLEEP STAGES
    deep_target_mins: float = 90.0
    rem_target_mins: float = 90.0
    deep_weight: float = 0.5
    rem_weight: float = 0.5

    # SLEEP CONSISTENCY
    consistency_grace_period_mins: float = 15.0
    max_late_penalty_window_mins: float = 105.0
    max_early_penalty_window_mins: float = 105.0
    max_early_penalty_points: float = 20.0
    rolling_window_nights: int = 14

    # INTERRUPTIONS
    duration_weight_points: float = 80.0
    frequency_weight_points: float = 20.0
    freq_score_fractions: tuple[float, ...] = (1.0, 1.0, 0.75, 0.5, 0.0)
    interruptions_grace_period_mins: float = 20.0
    max_penalty_window_mins: float = 70.0
    significant_wake_threshold_mins: float = 5.0


sleep_config = SleepScoreConfig()


# HRV RESILIENCE SCORE


class ResilienceScoreConfig(BaseModel):
    lookback_days: int = Field(default=7, ge=1)
    min_days_required: int = Field(default=5, ge=2)
    min_rr_samples: int = Field(default=20, ge=2)

    # 0-100 SCORING — linear mapping of HRV-CV (expressed as %)
    # cv_ceiling: upper bound for a perfect 100; anything at or below scores 100
    # cv_floor:   lower bound for a zero score; anything at or above scores 0
    # Between ceiling and floor the score drops linearly.
    cv_ceiling: float = Field(default=7.0)
    cv_floor: float = Field(default=40.0)

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        if self.min_days_required > self.lookback_days:
            msg = "min_days_required must be <= lookback_days"
            raise ValueError(msg)
        return self


resilience_config = ResilienceScoreConfig()
