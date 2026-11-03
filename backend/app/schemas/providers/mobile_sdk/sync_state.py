# ruff: noqa: N815

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.sync_status import DataTypeKind


class CoveredRange(BaseModel):
    startDate: datetime = Field(
        description="Earliest data held for this type. The SDK exports newest first, so an unfinished "
        "type resumes from here, backwards."
    )
    endDate: datetime = Field(description="Latest data held for this type.")


class SDKDataTypeSyncState(BaseModel):
    """What the server holds for one data type from this provider."""

    type: str = Field(
        description="Canonical data type: a series type slug (e.g. `heart_rate`) or an event category "
        "(`sleep`, `workout`).",
        examples=["heart_rate"],
    )
    kind: DataTypeKind = Field(description="`series` for time series samples, `event` for sleep and workouts.")
    historicalSyncCompleted: bool | None = Field(
        description="Whether a historical export finished this type. When false, resume it backwards "
        "from `coveredRange.startDate`. Null when no historical export reported this type, e.g. on SDK "
        "versions that do not send `syncSessionId`.",
    )
    lastSyncedAt: datetime = Field(description="When data of this type was last written on the server.")
    coveredRange: CoveredRange


class SDKSyncState(BaseModel):
    """Where the server says a user's SDK sync for one provider stands.

    The server is the source of truth: a device that lost its local state (e.g. after a
    logout) reads this to know where to resume from.
    """

    provider: str = Field(description="Canonical SDK provider slug.", examples=["apple"])
    historicalSyncCompleted: bool | None = Field(
        description="Whether a historical export for this provider has finished every data type it covered. "
        "False when one exists but has not finished. Null when there is no historical export on record: "
        "nothing synced yet, or an SDK version that does not send `syncSessionId`.",
    )
    syncedUntil: datetime | None = Field(
        description=(
            "Newest data held from this provider, across all types: where live sync continues from. "
            "Null when nothing has been synced yet."
        ),
        examples=["2026-11-01T22:15:00Z"],
    )
    dataTypes: list[SDKDataTypeSyncState] = Field(
        default_factory=list,
        description="Data held per type from this provider. Empty when nothing has been synced yet.",
    )
