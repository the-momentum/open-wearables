from app.constants.sleep import SleepStageType

# Withings Sleep v2 - Get `state`. 4 and 5 are sleep without stage detail; 15 is awake.
SLEEP_STATE_STAGE_MAP: dict[int, SleepStageType] = {
    0: SleepStageType.AWAKE,
    1: SleepStageType.LIGHT,
    2: SleepStageType.DEEP,
    3: SleepStageType.REM,
    4: SleepStageType.SLEEPING,
    5: SleepStageType.SLEEPING,
    15: SleepStageType.AWAKE,
}
