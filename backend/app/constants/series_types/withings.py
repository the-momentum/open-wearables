from app.constants.sleep import SleepStageType

# Withings Sleep v2 - Get `state`. 4 (manual) and 5 (unspecified) mean asleep with no
# stage detail; 15 (out of bed) counts as awake, since the user is not asleep.
SLEEP_STATE_STAGE_MAP: dict[int, SleepStageType] = {
    0: SleepStageType.AWAKE,
    1: SleepStageType.LIGHT,
    2: SleepStageType.DEEP,
    3: SleepStageType.REM,
    4: SleepStageType.SLEEPING,
    5: SleepStageType.SLEEPING,
    15: SleepStageType.AWAKE,
}
