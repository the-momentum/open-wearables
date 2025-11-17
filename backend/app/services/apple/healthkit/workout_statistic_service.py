from logging import Logger, getLogger

from app.models import WorkoutStatistic
from app.repositories import WorkoutStatisticRepository
from app.schemas import HKWorkoutStatisticCreate, HKWorkoutStatisticUpdate
from app.services.services import AppService

class WorkoutStatisticService(AppService[WorkoutStatisticRepository, WorkoutStatistic, HKWorkoutStatisticCreate, HKWorkoutStatisticUpdate]):
    """Service for workout statistics business logic."""
    
    def __init__(
        self,
        log: Logger,
        **kwargs,
    ):
        super().__init__(
            crud_model=WorkoutStatisticRepository,
            model=WorkoutStatistic,
            log=log,
            **kwargs
        )
    


workout_statistic_service = WorkoutStatisticService(log=getLogger(__name__))