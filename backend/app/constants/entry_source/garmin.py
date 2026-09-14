from app.schemas.enums import EntrySource


def get_unified_entry_source(manual: bool | None, is_web_upload: bool | None) -> EntrySource | None:
    """Convert Garmin's `manual`/`isWebUpload` activity flags to the unified EntrySource.

    `manual` marks a hand-typed Connect entry on the `activities` summaries we ingest - but
    not in `manuallyUpdatedActivities` (Activity API 1.2.4 s7.2), a type we don't ingest,
    where it marks a device recording the user merely edited and keeps full sensor data.
    """
    if manual is None and is_web_upload is None:
        return None
    return EntrySource.MANUAL if manual else EntrySource.AUTOMATIC
