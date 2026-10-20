from enum import StrEnum


class AggregateOrigin(StrEnum):
    """Who computed an aggregate: the provider (EXTERNAL) or Open Wearables from stored samples (INTERNAL)."""

    EXTERNAL = "external"
    INTERNAL = "internal"
