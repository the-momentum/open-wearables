from app.schemas.enums import EntrySource


def get_unified_entry_source(manual: bool | None) -> EntrySource | None:
    """Convert Strava's `manual` activity flag to the unified EntrySource.

    Returns None when Strava didn't report the flag.
    """
    if manual is None:
        return None
    return EntrySource.MANUAL if manual else EntrySource.AUTOMATIC
