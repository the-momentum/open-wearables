from enum import StrEnum


class HealthScoreCategory(StrEnum):
    SLEEP = "sleep"
    RECOVERY = "recovery"
    READINESS = "readiness"
    ACTIVITY = "activity"
    # The activity of the day before, recorded on the day after it: a category of its own, so a client never shows it as
    # the same activity as a provider's score of that day
    PREVIOUS_DAY_ACTIVITY = "previous_day_activity"
    STRESS = "stress"
    RESILIENCE = "resilience"
    BODY_BATTERY = "body_battery"
    STRAIN = "strain"


# Optional human-readable descriptions surfaced in the coverage matrix (tooltips).
# Only categories with a meaningful clarification need an entry; others default to "".
HEALTH_SCORE_DESCRIPTION_BY_ENUM: dict[HealthScoreCategory, str] = {
    HealthScoreCategory.BODY_BATTERY: "Daily peak body battery value",
}
