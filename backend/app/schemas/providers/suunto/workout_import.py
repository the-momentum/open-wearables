from pydantic import BaseModel, Field


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
    """Suunto device/gear information."""

    manufacturer: str | None = None
    name: str | None = None
    displayName: str | None = None
    serialNumber: str | None = None
    swVersion: str | None = None
    hwVersion: str | None = None


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
    # Suunto reports distance in meters as a float (e.g. 21381.4); keep it float so
    # fractional values don't fail Pydantic's int_from_float validation. Downstream
    # consumers already store it as Decimal(str(...)).
    totalDistance: float | None = None
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


class RootJSON(BaseModel):
    error: str | None = None
    payload: list[WorkoutJSON]
