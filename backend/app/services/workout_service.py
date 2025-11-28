from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import Workout
from app.repositories import WorkoutRepository
from app.schemas import (
    WorkoutCreate,
    WorkoutQueryParams,
    WorkoutStatisticResponse,
    WorkoutResponse,
    WorkoutUpdate,
)
from app.services.services import AppService
from app.services.workout_statistic_service import workout_statistic_service
from app.utils.exceptions import handle_exceptions


class WorkoutService(AppService[WorkoutRepository, Workout, WorkoutCreate, WorkoutUpdate]):
    """Service for HealthKit workout-related business logic."""

    def __init__(self, log: Logger, **kwargs):
        super().__init__(crud_model=WorkoutRepository, model=Workout, log=log, **kwargs)

    @handle_exceptions
    async def _get_workouts_with_filters(
        self,
        db_session: DbSession,
        query_params: WorkoutQueryParams,
        user_id: str,
    ) -> tuple[list[Workout], int]:
        """
        Get workouts with filtering, sorting, and pagination.
        Includes business logic and logging.
        """
        self.logger.debug(f"Fetching HealthKit workouts with filters: {query_params.model_dump()}")

        workouts, total_count = self.crud.get_workouts_with_filters(db_session, query_params, user_id)

        self.logger.debug(f"Retrieved {len(workouts)} HealthKit workouts out of {total_count} total")

        return workouts, total_count

    @handle_exceptions
    async def _get_workout_with_summary(self, db_session: DbSession, workout_id: UUID) -> tuple[Workout | None, dict]:
        """
        Get a single workout with its summary statistics.
        """
        self.logger.debug(f"Fetching HealthKit workout {workout_id} with summary")

        workout = self.get(db_session, workout_id, raise_404=True)
        summary = self.crud.get_workout_summary(db_session, workout_id)

        self.logger.debug(f"Retrieved HealthKit workout {workout_id} with summary data")

        return workout, summary

    @handle_exceptions
    async def get_workouts_response(
        self,
        db_session: DbSession,
        query_params: WorkoutQueryParams,
        user_id: str,
    ) -> list[WorkoutResponse]:
        """
        Get HealthKit workouts formatted as API response.

        Returns:
            list[WorkoutResponse] ready for API
        """
        workouts, _ = await self._get_workouts_with_filters(db_session, query_params, user_id)

        workout_responses = []
        for workout in workouts:
            statistics = await workout_statistic_service.get_workout_statistics(db_session, user_id, workout.id)

            workout_response = WorkoutResponse(
                id=workout.id,
                type=workout.type,
                duration_seconds=workout.duration_seconds,
                source_name=workout.source_name,    
                start_datetime=workout.start_datetime,
                end_datetime=workout.end_datetime,
                statistics=statistics,
            )
            workout_responses.append(workout_response)

        return workout_responses


workout_service = WorkoutService(log=getLogger(__name__))
