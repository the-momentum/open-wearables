from pydantic import BaseModel


class HeartRateJSON(BaseModel):
    workoutMaxHR: int
    workoutAvgHR: int
    userMaxHR: int
    avg: int
    hrmax: int
    max: int


class DeviceJSON(BaseModel):
    manufacturer: str
    name: str
    displayName: str
    serialNumber: str
    # some more stuff, like software version, etc.


class WorkoutJSON(BaseModel):
    workoutId: int
    # unix timestamp (ms)
    startTime: int
    stopTime: int
    # seconds
    totalTime: int

    totalDistance: int
    stepCount: int
    energyConsumption: int

    hrdata: HeartRateJSON

    gear: DeviceJSON | None = None


class RootJSON(BaseModel):
    error: str | None = None
    payload: list[WorkoutJSON]
