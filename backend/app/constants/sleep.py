from enum import StrEnum


class SleepStageType(StrEnum):
    IN_BED = "in_bed"
    AWAKE = "awake"
    LIGHT = "light"
    DEEP = "deep"
    REM = "rem"
    UNKNOWN = "unknown"
