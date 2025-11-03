from datetime import datetime
from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import Workout
from app.repositories import HKWorkoutRepository
from app.schemas import (
    HKWorkoutQueryParams,
    HKWorkoutCreate,
    HKWorkoutUpdate,
    HKWorkoutListResponse,
    HKWorkoutResponse,
    HKWorkoutSummary,
    HKWorkoutMeta,
    HKDateRange,
)
from app.services.services import AppService
from app.utils.exceptions import handle_exceptions


class WorkoutService(AppService[HKWorkoutRepository, Workout, HKWorkoutCreate, HKWorkoutUpdate]):
    """Service for HealthKit workout-related business logic."""

    def __init__(self, log: Logger, **kwargs):
        super().__init__(
            crud_model=HKWorkoutRepository,
            model=Workout,
            log=log,
            **kwargs
        )

    @handle_exceptions
    async def _get_workouts_with_filters(
        self, 
        db_session: DbSession, 
        query_params: HKWorkoutQueryParams,
        user_id: str
    ) -> tuple[list[Workout], int]:
        """
        Get workouts with filtering, sorting, and pagination.
        Includes business logic and logging.
        """
        self.logger.debug(f"Fetching HealthKit workouts with filters: {query_params.model_dump()}")
        
        workouts, total_count = self.crud.get_workouts_with_filters(
            db_session, query_params, user_id
        )
        
        self.logger.debug(f"Retrieved {len(workouts)} HealthKit workouts out of {total_count} total")
        
        return workouts, total_count

    @handle_exceptions
    async def _get_workout_with_summary(
        self,
        db_session: DbSession,
        workout_id: UUID
    ) -> tuple[Workout | None, dict]:
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
        query_params: HKWorkoutQueryParams,
        user_id: str
    ) -> HKWorkoutListResponse:
        """
        Get HealthKit workouts formatted as API response.
        
        Returns:
            HKWorkoutListResponse ready for API
        """
        workouts, total_count = await self._get_workouts_with_filters(db_session, query_params, user_id)
        
        workout_responses = []
        for workout in workouts:
            _, summary_data = await self._get_workout_with_summary(db_session, workout.id)
            
            workout_response = HKWorkoutResponse(
                id=workout.id,
                type=workout.type,
                startDate=workout.startDate,
                endDate=workout.endDate,
                duration=float(workout.duration),
                durationUnit=workout.durationUnit,
                sourceName=workout.sourceName,
                user_id=workout.user_id,
                summary=HKWorkoutSummary(**summary_data),
            )
            workout_responses.append(workout_response)

        start_date_str = query_params.start_date or "1900-01-01T00:00:00Z"
        end_date_str = query_params.end_date or datetime.now().isoformat() + "Z"
        
        start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        duration_days = (end_date - start_date).days
        
        meta = HKWorkoutMeta(
            requested_at=datetime.now().isoformat() + "Z",
            filters=query_params.model_dump(exclude_none=True),
            result_count=total_count,
            total_count=total_count,
            date_range=HKDateRange(
                start=start_date_str,
                end=end_date_str,
                duration_days=duration_days,
            ),
        )

        return HKWorkoutListResponse(
            data=workout_responses,
            meta=meta,
        )


workout_service = WorkoutService(log=getLogger(__name__))
