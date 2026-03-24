from datetime import datetime

from pydantic import BaseModel, Field

from app.constants.series_types.apple import SleepPhase
from app.constants.sleep import SleepStageType


class SleepStateStage(BaseModel):
    stage: SleepStageType
    start_time: datetime
    end_time: datetime


class SleepState(BaseModel):
    """Schema for sleep state stored in Redis."""

    uuid: str
    source_name: str | None = None
    device_model: str | None = None
    provider: str | None = None
    zone_offset: str | None = None

    start_time: datetime
    end_time: datetime

    last_start_timestamp: datetime
    last_end_timestamp: datetime

    # Tracks when this state was last written to Redis. Used for stale detection
    # instead of end_time so that bulk historical uploads (where end_time is many
    # hours in the past) are not prematurely finalized between consecutive payloads.
    last_updated_at: datetime | None = None

    in_bed_seconds: float = 0
    awake_seconds: float = 0
    sleeping_seconds: float = 0
    light_seconds: float = 0
    deep_seconds: float = 0
    rem_seconds: float = 0

    stages: list[SleepStateStage] = Field(default_factory=list)


SLEEP_START_STATES = {
    SleepPhase.IN_BED,
    SleepPhase.SLEEPING,
    SleepPhase.ASLEEP_LIGHT,
    SleepPhase.ASLEEP_DEEP,
    SleepPhase.ASLEEP_REM,
}
