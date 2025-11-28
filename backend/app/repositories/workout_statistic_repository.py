from uuid import UUID

from app.database import DbSession
from app.models import WorkoutStatistic
from app.repositories.repositories import CrudRepository
from app.schemas import WorkoutStatisticCreate, WorkoutStatisticUpdate


class WorkoutStatisticRepository(CrudRepository[WorkoutStatistic, WorkoutStatisticCreate, WorkoutStatisticUpdate]):
    """Repository for workout statistics database operations."""

    def __init__(self, model: type[WorkoutStatistic]):
        super().__init__(model)

    def get_workout_statistics(self, db_session: DbSession, user_id: str, workout_id: str) -> list[WorkoutStatistic]:
        return (
            db_session.query(self.model)
            .filter(self.model.user_id == user_id, self.model.workout_id == workout_id)
            .all()
        )
        
    def get_workout_heart_rate_statistics(self, db_session: DbSession, user_id: str, workout_id: str) -> list[WorkoutStatistic]:
        return (
            db_session.query(self.model)
            .filter(self.model.user_id == user_id, self.model.workout_id == workout_id, self.model.type == "heartRate")
            .all()
        )
        
    def get_user_heart_rate_statistics(self, db_session: DbSession, user_id: str) -> list[WorkoutStatistic]:
        return (
            db_session.query(self.model)
            .filter(self.model.user_id == user_id, self.model.type == "heartRate")
            .all()
        )

