from enum import StrEnum


class LiveSyncMode(StrEnum):
    PULL = "pull"
    WEBHOOK = "webhook"
