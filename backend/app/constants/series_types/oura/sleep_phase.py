from app.constants.sleep import SleepStageType

SLEEP_PHASE_MAP = {
    "1": SleepStageType.DEEP,
    "2": SleepStageType.LIGHT,
    "3": SleepStageType.REM,
    "4": SleepStageType.AWAKE,
}
