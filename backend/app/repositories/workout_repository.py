from app.models.workout import Workout
from app.repositories.repositories import CrudRepository
from app.schemas.workout import WorkoutCreate, WorkoutUpdate


class WorkoutRepository(CrudRepository[Workout, WorkoutCreate, WorkoutUpdate]):
    """Repository for managing Workout entities."""

    def __init__(self):
        super().__init__(Workout)
