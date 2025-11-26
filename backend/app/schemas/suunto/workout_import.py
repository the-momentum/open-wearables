from pydantic import BaseModel

    
class HeartRateJSON(BaseModel):
    workoutMaxHR: int   
    workoutAvgHR: int
    userMaxHR: int
    avg: int
    hrmax: int
    max: int


class WorkoutJSON(BaseModel):
    workoutId: str
    # unix timestamp (ms)
    startTime: int
    stopTime: int
    # seconds
    totalTime: int
    
    totalDistance: int
    stepCount: int
    energyConsumption: int
    
    hrdata: HeartRateJSON
    