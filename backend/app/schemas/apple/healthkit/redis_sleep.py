from typing import TypedDict

from app.constants.series_types import SleepType


class SleepState(TypedDict):
    """Schema for sleep state."""

    uuid: str
    source_name: str | None
    start_time: str
    last_type: int
    last_timestamp: str

    in_bed: int
    awake: int
    light: int
    deep: int
    rem: int


SLEEP_START_STATES = {
    SleepType.IN_BED,
    SleepType.ASLEEP_UNSPECIFIED,
    SleepType.ASLEEP_CORE,
    SleepType.ASLEEP_DEEP,
    SleepType.ASLEEP_REM,
}
