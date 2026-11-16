from enum import StrEnum


class SleepStageType(StrEnum):
    IN_BED = "in_bed"
    AWAKE = "awake"
    SLEEPING = "sleeping"
    LIGHT = "light"
    DEEP = "deep"
    REM = "rem"
    UNKNOWN = "unknown"


ASLEEP_STAGES = frozenset({SleepStageType.SLEEPING, SleepStageType.LIGHT, SleepStageType.DEEP, SleepStageType.REM})
