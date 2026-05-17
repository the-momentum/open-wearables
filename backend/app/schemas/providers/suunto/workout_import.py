from typing import Annotated, Any, Literal

from pydantic import AliasChoices, BaseModel, Discriminator, Field, Tag


class PauseMarker(BaseModel):
    """Single pause segment delivered by Suunto's PauseMarkerExtension."""

    startTime: int  # ms since epoch
    endTime: int  # ms since epoch
    automatic: bool = False

    @property
    def duration_ms(self) -> int:
        return max(0, self.endTime - self.startTime)


class HeartRateJSON(BaseModel):
    """Suunto heart rate data from workout.

    Note: 'max' is userMaxHR (from user settings), 'hrmax' is actual max HR during workout.
    """

    workoutMaxHR: int | None = None  # Actual max HR during workout (alternative field)
    workoutAvgHR: int | None = None  # Actual avg HR during workout (alternative field)
    userMaxHR: int | None = None  # User's max HR from settings
    avg: int | None = None  # Average HR during workout
    hrmax: int | None = None  # Actual maximum HR during workout (THIS IS THE CORRECT ONE)
    max: int | None = None  # User's max HR from settings (DON'T USE FOR workout max)
    min: int | None = None  # Minimum HR during workout


class DeviceJSON(BaseModel):
    """Suunto device/gear information.

    Suunto inconsistently labels firmware/hardware version: the legacy top-level
    `gear` block uses `swVersion`/`hwVersion`, while the newer `SummaryExtension.gear`
    block uses `softwareVersion`/`hardwareVersion`. Accept both spellings.
    """

    manufacturer: str | None = None
    name: str | None = None
    displayName: str | None = None
    serialNumber: str | None = None
    swVersion: str | None = Field(default=None, validation_alias=AliasChoices("swVersion", "softwareVersion"))
    hwVersion: str | None = Field(default=None, validation_alias=AliasChoices("hwVersion", "hardwareVersion"))


class PauseMarkerExtension(BaseModel):
    """Carries pause segments so we can compute real elapsed time including pauses."""

    type: Literal["PauseMarkerExtension"]
    pauseMarkers: list[PauseMarker] | None = None


class SummaryExtension(BaseModel):
    """Newer Suunto watches (Race 2 and later) ship gear info here instead of at the workout root."""

    type: Literal["SummaryExtension"]
    gear: DeviceJSON | None = None


class UnknownExtension(BaseModel):
    """Catch-all for extension types we don't parse.

    Suunto can return extension types we didn't request, or new ones in the future.
    Routing them here keeps the discriminated union from rejecting valid payloads.
    """

    type: str


def _extension_discriminator(value: Any) -> str:
    """Return the discriminator tag for an extension dict or model instance."""
    raw_type = value.get("type") if isinstance(value, dict) else getattr(value, "type", None)
    if raw_type in {"PauseMarkerExtension", "SummaryExtension"}:
        return raw_type
    return "unknown"


WorkoutExtension = Annotated[
    Annotated[PauseMarkerExtension, Tag("PauseMarkerExtension")]
    | Annotated[SummaryExtension, Tag("SummaryExtension")]
    | Annotated[UnknownExtension, Tag("unknown")],
    Discriminator(_extension_discriminator),
]


REQUESTED_WORKOUT_EXTENSIONS: tuple[str, ...] = (
    "PauseMarkerExtension",
    "SummaryExtension",
)


class WorkoutJSON(BaseModel):
    """Suunto workout data from API."""

    workoutId: int
    activityId: int

    # Unix timestamp (ms)
    startTime: int
    # Sometimes missing in fresh webhook payloads (Suunto computes it asynchronously);
    # callers fall back to startTime + totalTime when None.
    stopTime: int | None = None
    # Seconds
    totalTime: float
    timeOffsetInMinutes: int | None = None

    # Metrics (all optional)
    totalDistance: int | None = None
    stepCount: int | None = None
    energyConsumption: int | None = None

    # Speed metrics (m/s)
    maxSpeed: float | None = None
    avgSpeed: float | None = None

    # Elevation (meters)
    totalAscent: float | None = None
    totalDescent: float | None = None
    maxAltitude: float | None = None
    minAltitude: float | None = None

    # Power (watts)
    avgPower: float | None = None
    maxPower: float | None = None

    # Cadence
    avgCadence: float | None = None
    maxCadence: float | None = None

    # Heart rate data
    hrdata: HeartRateJSON | None = None

    # Device info (gear = watch)
    gear: DeviceJSON | None = None

    # Workout name/notes
    workoutName: str | None = Field(default=None, alias="name")
    notes: str | None = None

    # Discriminated by `type`; unknown types route to UnknownExtension so the schema
    # never rejects unexpected payloads from Suunto.
    extensions: list[WorkoutExtension] | None = None

    @property
    def pause_markers(self) -> list[PauseMarker]:
        for ext in self.extensions or []:
            if isinstance(ext, PauseMarkerExtension):
                return ext.pauseMarkers or []
        return []

    @property
    def gear_from_summary_extension(self) -> DeviceJSON | None:
        for ext in self.extensions or []:
            if isinstance(ext, SummaryExtension):
                return ext.gear
        return None


class RootJSON(BaseModel):
    error: str | None = None
    payload: list[WorkoutJSON]
