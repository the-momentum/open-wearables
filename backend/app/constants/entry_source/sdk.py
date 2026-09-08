from app.schemas.enums import EntrySource
from app.schemas.providers.mobile_sdk.sync_request import RecordingMethod

# ACTIVE ("user started a recording session") and AUTOMATIC ("the platform detected it")
# are both device-measured, so both collapse to AUTOMATIC.
RECORDING_METHOD_TO_UNIFIED: dict[RecordingMethod, EntrySource] = {
    RecordingMethod.ACTIVE: EntrySource.AUTOMATIC,
    RecordingMethod.AUTOMATIC: EntrySource.AUTOMATIC,
    RecordingMethod.MANUAL: EntrySource.MANUAL,
    RecordingMethod.UNKNOWN: EntrySource.UNKNOWN,
}


def get_unified_entry_source(recording_method: RecordingMethod | str | None) -> EntrySource | None:
    """Convert the mobile SDK's `source.recordingMethod` to the unified EntrySource."""
    if recording_method is None:
        return None
    try:
        known = RecordingMethod(recording_method)
    except ValueError:
        return EntrySource.UNKNOWN
    return RECORDING_METHOD_TO_UNIFIED.get(known, EntrySource.UNKNOWN)
