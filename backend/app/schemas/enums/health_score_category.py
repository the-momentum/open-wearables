from enum import StrEnum


class HealthScoreCategory(StrEnum):
    SLEEP = "sleep"
    RECOVERY = "recovery"
    READINESS = "readiness"
    ACTIVITY = "activity"
    STRESS = "stress"
    BODY_BATTERY = "body_battery"
    STRAIN = "strain"
