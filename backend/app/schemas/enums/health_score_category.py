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


# Optional human-readable descriptions surfaced in the coverage matrix (tooltips).
# Only categories with a meaningful clarification need an entry; others default to "".
HEALTH_SCORE_DESCRIPTION_BY_ENUM: dict[HealthScoreCategory, str] = {
    HealthScoreCategory.BODY_BATTERY: "Daily peak body battery value",
}
