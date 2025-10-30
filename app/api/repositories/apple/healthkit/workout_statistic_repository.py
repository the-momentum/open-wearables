from app.models import WorkoutStatistic
from app.repositories import CrudRepository
from app.schemas import HKWorkoutStatisticCreate, HKWorkoutStatisticUpdate


class WorkoutStatisticRepository(CrudRepository[WorkoutStatistic, HKWorkoutStatisticCreate, HKWorkoutStatisticUpdate]):
    """Repository for workout statistics database operations."""
    
    def __init__(self, model: type[WorkoutStatistic]):
        super().__init__(model)
