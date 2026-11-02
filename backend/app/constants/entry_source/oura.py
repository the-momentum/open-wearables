from app.schemas.enums import EntrySource

# Oura's PublicWorkoutSource enum. Oura extends it without a changelog (1.40 added the two
# live_* values), so keep the UNKNOWN fallback for values we have not mapped yet.
OURA_SOURCE_TO_UNIFIED: dict[str, EntrySource] = {
    "manual": EntrySource.MANUAL,
    "autodetected": EntrySource.AUTOMATIC,
    "confirmed": EntrySource.AUTOMATIC,
    "workout_heart_rate": EntrySource.AUTOMATIC,
    "live_third_party_heart_rate": EntrySource.AUTOMATIC,
    "live_oura_heart_rate": EntrySource.AUTOMATIC,
}


def get_unified_entry_source(oura_source: str | None) -> EntrySource | None:
    """Convert Oura's workout `source` field to the unified EntrySource."""
    if oura_source is None:
        return None
    return OURA_SOURCE_TO_UNIFIED.get(oura_source, EntrySource.UNKNOWN)
