from enum import StrEnum

from app.constants.sleep import SleepStageType


class SleepPhase(StrEnum):
    IN_BED = SleepStageType.IN_BED
    SLEEPING = "sleeping"
    AWAKE = SleepStageType.AWAKE
    ASLEEP_LIGHT = SleepStageType.LIGHT
    ASLEEP_DEEP = SleepStageType.DEEP
    ASLEEP_REM = SleepStageType.REM
    UNKNOWN = SleepStageType.UNKNOWN


def get_apple_sleep_phase(apple_sleep_phase: str) -> SleepPhase | None:
    try:
        return SleepPhase(apple_sleep_phase)
    except ValueError:
        return None
