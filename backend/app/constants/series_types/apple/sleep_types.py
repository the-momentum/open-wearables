from enum import StrEnum


class SleepPhase(StrEnum):
    IN_BED = "in_bed"
    SLEEPING = "sleeping"
    AWAKE = "awake"
    ASLEEP_LIGHT = "light"
    ASLEEP_DEEP = "deep"
    ASLEEP_REM = "rem"
    UNKOWN = "unknown"


def get_apple_sleep_phase(apple_sleep_phase: str) -> SleepPhase | None:
    try:
        return SleepPhase(apple_sleep_phase)
    except ValueError:
        return None
