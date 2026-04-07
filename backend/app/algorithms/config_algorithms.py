"""Default configuration values for health score algorithms."""

from pydantic import BaseModel


# SLEEP SCORE


class SleepMasterWeightsConfig(BaseModel):
    duration: float = 0.40
    stages: float = 0.20
    consistency: float = 0.20
    interruptions: float = 0.20


class SleepConsistencyConfig(BaseModel):
    base_score: float = 100.0
    grace_period_mins: float = 15.0
    max_late_penalty_window_mins: float = 105.0
    max_early_penalty_window_mins: float = 105.0
    max_early_penalty_points: float = 20.0
    rolling_window_nights: int = 14


class SleepInterruptionsConfig(BaseModel):
    duration_weight_points: float = 80.0
    frequency_weight_points: float = 20.0
    grace_period_mins: float = 20.0
    max_penalty_window_mins: float = 70.0
    significant_wake_threshold_mins: float = 5.0


sleep_master_weights_config = SleepMasterWeightsConfig()
sleep_consistency_config = SleepConsistencyConfig()
sleep_interruptions_config = SleepInterruptionsConfig()
