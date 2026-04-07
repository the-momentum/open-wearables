"""Default configuration values for health score algorithms."""

from pydantic import BaseModel

# HRV RECOVERY SCORE


class RecoveryScoreConfig(BaseModel):
    lookback_days: int = 7
    min_days_required: int = 5
    min_rr_samples: int = 20


recovery_config = RecoveryScoreConfig()
