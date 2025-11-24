from app.models import WorkoutStatistic
from app.repositories.repositories import CrudRepository
from app.schemas import WorkoutStatisticCreate, WorkoutStatisticUpdate


class WorkoutStatisticRepository(CrudRepository[WorkoutStatistic, WorkoutStatisticCreate, WorkoutStatisticUpdate]):
    """Repository for workout statistics database operations."""

    def __init__(self, model: type[WorkoutStatistic]):
        super().__init__(model)
