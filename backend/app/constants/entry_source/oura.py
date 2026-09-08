from app.schemas.enums import EntrySource

# Oura's PublicWorkoutSource enum (closed), so UNKNOWN below is purely defensive.
OURA_SOURCE_TO_UNIFIED: dict[str, EntrySource] = {
    "manual": EntrySource.MANUAL,
    "autodetected": EntrySource.AUTOMATIC,
    "confirmed": EntrySource.AUTOMATIC,
    "workout_heart_rate": EntrySource.AUTOMATIC,
}


def get_unified_entry_source(oura_source: str | None) -> EntrySource | None:
    """Convert Oura's workout `source` field to the unified EntrySource."""
    if oura_source is None:
        return None
    return OURA_SOURCE_TO_UNIFIED.get(oura_source, EntrySource.UNKNOWN)
