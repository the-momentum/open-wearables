from app.constants.sleep import SleepStageType

# Sensor Bio /v1/sleep/details/day -> sleep_stages[].status
SLEEP_STATUS_STAGE_MAP: dict[str, SleepStageType] = {
    "light": SleepStageType.LIGHT,
    "deep": SleepStageType.DEEP,
    "rem": SleepStageType.REM,
    "awake": SleepStageType.AWAKE,
}
