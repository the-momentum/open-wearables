from enum import StrEnum


class SdkConnectionOutcome(StrEnum):
    """What ``ensure_sdk_connection`` did, so the caller can emit the right event.

    SDK providers have no OAuth callback to hang ``connection.created`` off, so the
    connection row is created lazily on first upload. The repository reports which
    branch it took because the upload path runs on every batch: only CREATED and
    REACTIVATED are state changes worth emitting, EXISTING is the steady state.
    """

    CREATED = "created"
    REACTIVATED = "reactivated"
    EXISTING = "existing"
