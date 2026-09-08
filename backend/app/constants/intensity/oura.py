from app.schemas.enums import WorkoutIntensity

# Oura's PublicWorkoutIntensity enum (closed), so UNKNOWN below is purely defensive.
OURA_INTENSITY_TO_UNIFIED: dict[str, WorkoutIntensity] = {
    "easy": WorkoutIntensity.LOW,
    "moderate": WorkoutIntensity.MODERATE,
    "hard": WorkoutIntensity.HIGH,
}


def get_unified_intensity(oura_intensity: str | None) -> WorkoutIntensity | None:
    """Convert Oura's workout `intensity` field to the unified WorkoutIntensity."""
    if oura_intensity is None:
        return None
    return OURA_INTENSITY_TO_UNIFIED.get(oura_intensity, WorkoutIntensity.UNKNOWN)
