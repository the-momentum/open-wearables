from app.schemas.enums import EntrySource


def get_unified_entry_source(manual: bool | None, is_web_upload: bool | None) -> EntrySource | None:
    """Convert Garmin's `manual`/`isWebUpload` activity flags to the unified EntrySource.

    Returns None when Garmin reported neither flag.
    """
    if manual is None and is_web_upload is None:
        return None
    return EntrySource.MANUAL if manual else EntrySource.AUTOMATIC
