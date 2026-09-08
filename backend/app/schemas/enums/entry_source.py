from enum import StrEnum


class EntrySource(StrEnum):
    """Unified provenance of a workout record, independent of the reporting provider.

    MANUAL is only for self-reported entries with no device measurements behind them; a file
    recorded on another device and uploaded later is still measured data, so it counts as
    AUTOMATIC. See app.constants.entry_source for the per-provider mappings.
    """

    MANUAL = "manual"
    AUTOMATIC = "automatic"
    UNKNOWN = "unknown"
