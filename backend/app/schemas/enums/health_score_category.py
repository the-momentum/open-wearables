from enum import StrEnum


class HealthScoreCategory(StrEnum):
    SLEEP = "sleep"
    RECOVERY = "recovery"
    READINESS = "readiness"
    ACTIVITY = "activity"
    STRESS = "stress"
    RESILIENCE = "resilience"
    BODY_BATTERY = "body_battery"
    STRAIN = "strain"
