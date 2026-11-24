from enum import StrEnum


class ComputedBy(StrEnum):
    """Who computed an aggregate: the provider, or Open Wearables from stored samples."""

    PROVIDER = "provider"
    OPEN_WEARABLES = "open_wearables"
