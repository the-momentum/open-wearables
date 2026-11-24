from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.constants.series_types.sdk import SleepPhase
from app.constants.sleep import ASLEEP_STAGES, SleepStageType
from app.schemas.enums import DeviceType

# Stages a night can begin with, the stage types of SLEEP_START_STATES.
SLEEP_START_STAGES = ASLEEP_STAGES | {SleepStageType.IN_BED}


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
    # Whether a SLEEP_START_STAGES stage arrived; until then the session holds only awake.
    has_sleep_stage: bool = False

    in_bed_seconds: float = 0
    awake_seconds: float = 0
    sleeping_seconds: float = 0
    light_seconds: float = 0
    deep_seconds: float = 0
    rem_seconds: float = 0

    # Provider-computed sleep score sent in the SDK sleep entry `values` (Samsung `sleepScore`)
    sleep_score: float | None = None

    stages: list[SleepStateStage] = Field(default_factory=list)

    @model_validator(mode="after")
    def _derive_has_sleep_stage(self) -> Self:
        # A state saved before the flag existed gets it from its stages.
        if "has_sleep_stage" not in self.model_fields_set:
            self.has_sleep_stage = any(stage.stage in SLEEP_START_STAGES for stage in self.stages)
        return self


SLEEP_START_STATES = {
    SleepPhase.IN_BED,
    SleepPhase.SLEEPING,
    SleepPhase.ASLEEP_LIGHT,
    SleepPhase.ASLEEP_DEEP,
    SleepPhase.ASLEEP_REM,
}
