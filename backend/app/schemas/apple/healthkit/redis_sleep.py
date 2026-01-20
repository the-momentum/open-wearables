from typing import TypedDict

from app.constants.series_types import SleepPhase


class SleepState(TypedDict):
    """Schema for sleep state."""

    uuid: str
    source_name: str | None
    start_time: str
    last_timestamp: str

    in_bed: int
    awake: int
    light: int
    deep: int
    rem: int


SLEEP_START_STATES = {
    SleepPhase.IN_BED,
    SleepPhase.ASLEEP_UNSPECIFIED,
    SleepPhase.ASLEEP_CORE,
    SleepPhase.ASLEEP_DEEP,
    SleepPhase.ASLEEP_REM,
}
