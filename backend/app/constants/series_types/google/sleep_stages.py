from app.constants.sleep import SleepStageType

# Google Health API Sleep.SleepStageType -> unified SleepStageType.
GOOGLE_SLEEP_STAGE_MAP: dict[str, SleepStageType] = {
    "AWAKE": SleepStageType.AWAKE,
    "LIGHT": SleepStageType.LIGHT,
    "DEEP": SleepStageType.DEEP,
    "REM": SleepStageType.REM,
    "ASLEEP": SleepStageType.SLEEPING,
    "RESTLESS": SleepStageType.UNKNOWN,
}
