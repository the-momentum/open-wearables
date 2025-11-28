from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import WorkoutStatistic
from app.repositories import WorkoutStatisticRepository
from app.schemas import WorkoutStatisticCreate, WorkoutStatisticUpdate, WorkoutStatisticResponse
from app.services.services import AppService
from app.utils.exceptions import handle_exceptions


class WorkoutStatisticService(
    AppService[WorkoutStatisticRepository, WorkoutStatistic, WorkoutStatisticCreate, WorkoutStatisticUpdate],
):
    """Service for workout statistics business logic."""

    def __init__(
        self,
        log: Logger,
        **kwargs,
    ):
        super().__init__(crud_model=WorkoutStatisticRepository, model=WorkoutStatistic, log=log, **kwargs)

    @handle_exceptions
    async def get_workout_statistics(
        self,
        db_session: DbSession,
        user_id: str,
        workout_id: UUID,
    ) -> list[WorkoutStatisticResponse]:
        """
        Get workout statistics.
        """
        statistics = self.crud.get_workout_statistics(db_session, user_id, workout_id)
        return [
            WorkoutStatisticResponse(
                id=stat.id,
                user_id=stat.user_id,
                workout_id=stat.workout_id,
                type=stat.type,
                start_datetime=stat.start_datetime,
                end_datetime=stat.end_datetime,
                min=stat.min,
                max=stat.max,
                avg=stat.avg,
                unit=stat.unit,
            )
            for stat in statistics
        ]


    @handle_exceptions
    async def get_workout_heart_rate_statistics(
        self,
        db_session: DbSession,
        user_id: str,
        workout_id: UUID,
    ) -> list[WorkoutStatisticResponse]:
        """
        Get heart rate statistics.
        """
        statistics = self.crud.get_workout_heart_rate_statistics(db_session, user_id, workout_id)
        return [
            WorkoutStatisticResponse(
                id=stat.id,
                user_id=stat.user_id,
                workout_id=stat.workout_id,
                type=stat.type,
                start_datetime=stat.start_datetime,
                end_datetime=stat.end_datetime,
                min=stat.min,
                max=stat.max,
                avg=stat.avg,
                unit=stat.unit,
            )
            for stat in statistics
        ]
    
    
    @handle_exceptions
    async def get_user_heart_rate_statistics(
        self,
        db_session: DbSession,
        user_id: str,
    ) -> list[WorkoutStatisticResponse]:
        """
        Get user heart rate statistics.
        """
        statistics = self.crud.get_user_heart_rate_statistics(db_session, user_id)
        return [
            WorkoutStatisticResponse(
                id=stat.id,
                user_id=stat.user_id,
                workout_id=stat.workout_id,
                type=stat.type,
                start_datetime=stat.start_datetime,
                end_datetime=stat.end_datetime,
                min=stat.min,
                max=stat.max,
                avg=stat.avg,
                unit=stat.unit,
            )
            for stat in statistics
        ]
    
workout_statistic_service = WorkoutStatisticService(log=getLogger(__name__))
