from typing import TypedDict


class SleepState(TypedDict):
    """Schema for sleep state."""

    uuid: str
    start_time: str
    last_type: int
    last_timestamp: str

    in_bed: int
    awake: int
    light: int
    deep: int
    rem: int


SLEEP_START_STATES = {
    SleepState.IN_BED,
    SleepState.ASLEEP_UNSPECIFIED,
    SleepState.ASLEEP_CORE,
    SleepState.ASLEEP_DEEP,
    SleepState.ASLEEP_REM,
}
