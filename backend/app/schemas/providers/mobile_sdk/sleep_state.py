from datetime import datetime

from pydantic import BaseModel, Field

from app.constants.series_types.sdk import SleepPhase
from app.constants.sleep import SleepStageType
from app.schemas.enums import DeviceType


class SleepStateStage(BaseModel):
    stage: SleepStageType
    start_time: datetime
    end_time: datetime


class SleepState(BaseModel):
    """Schema for sleep state stored in Redis."""

    uuid: str
    source_name: str | None = None
    device_model: str | None = None
    device_type: DeviceType | None = None
    device_id: str | None = None
    source_app_id: str | None = None
    device_manufacturer: str | None = None
    provider: str | None = None
    zone_offset: str | None = None

    start_time: datetime
    end_time: datetime

    last_start_timestamp: datetime
    last_end_timestamp: datetime
    last_received_at: datetime | None = None
    has_apple_watch_sleep: bool = False

    in_bed_seconds: float = 0
    awake_seconds: float = 0
    sleeping_seconds: float = 0
    light_seconds: float = 0
    deep_seconds: float = 0
    rem_seconds: float = 0

    # Provider-computed sleep score sent in the SDK sleep entry `values` (Samsung `sleepScore`)
    sleep_score: float | None = None

    # False while the session holds only awake samples. Such a session is kept so
    # an awakening that opens an upload is not lost, but it is not a night on its own:
    # its source is replaced by the first sleep sample, and it is dropped if none comes.
    has_sleep_sample: bool = True

    stages: list[SleepStateStage] = Field(default_factory=list)


SLEEP_START_STATES = {
    SleepPhase.IN_BED,
    SleepPhase.SLEEPING,
    SleepPhase.ASLEEP_LIGHT,
    SleepPhase.ASLEEP_DEEP,
    SleepPhase.ASLEEP_REM,
}

# The same set in the stage domain, used on stored stages (SleepPhase values are SleepStageType values).
SLEEP_START_STAGES = {SleepStageType(phase) for phase in SLEEP_START_STATES}
