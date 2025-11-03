from datetime import datetime
from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import Workout
from app.repositories import AEWorkoutRepository
from app.schemas import (
    AEWorkoutQueryParams, 
    AEWorkoutCreate, 
    AEWorkoutUpdate,
    AEWorkoutListResponse,
    AEWorkoutResponse,
    AESummary,
    AEWorkoutMeta,
    AEDistanceValue,
    AEActiveEnergyValue,
    AEIntensityValue,
    AEDateRange,
)
from app.services.services import AppService
from app.utils.exceptions import handle_exceptions


class WorkoutService(AppService[AEWorkoutRepository, Workout, AEWorkoutCreate, AEWorkoutUpdate]):
    """Service for workout-related business logic."""

    def __init__(self, log: Logger, **kwargs):
        super().__init__(
            crud_model=AEWorkoutRepository,
            model=Workout,
            log=log,
            **kwargs
        )

    @handle_exceptions
    async def _get_workouts_with_filters(
        self, 
        db_session: DbSession, 
        query_params: AEWorkoutQueryParams,
        user_id: str
    ) -> tuple[list[Workout], int]:
        """
        Get workouts with filtering, sorting, and pagination.
        Includes business logic and logging.
        """
        self.logger.debug(f"Fetching workouts with filters: {query_params.model_dump()}")
        
        workouts, total_count = self.crud.get_workouts_with_filters(
            db_session, query_params, user_id
        )
        
        self.logger.debug(f"Retrieved {len(workouts)} workouts out of {total_count} total")
        
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
        self.logger.debug(f"Fetching workout {workout_id} with summary")
        
        workout = self.get(db_session, workout_id, raise_404=True)
        summary = self.crud.get_workout_summary(db_session, workout_id)
        
        self.logger.debug(f"Retrieved workout {workout_id} with summary data")
        
        return workout, summary

    @handle_exceptions
    async def get_workouts_response(
        self, 
        db_session: DbSession, 
        query_params: AEWorkoutQueryParams,
        user_id: str
    ) -> AEWorkoutListResponse:
        """
        Get workouts formatted as API response.
        
        Returns:
            WorkoutListResponse ready for API
        """
        # Get raw data
        workouts, total_count = await self._get_workouts_with_filters(db_session, query_params, user_id)
        
        # Convert workouts to response format
        workout_responses = []
        for workout in workouts:
            # Get summary data
            _, summary_data = await self._get_workout_with_summary(db_session, workout.id)
            
            # Build response object
            workout_response = AEWorkoutResponse(
                id=workout.id,
                name=workout.type or "Unknown Workout",
                location="Outdoor",
                start=workout.startDate.isoformat(),
                end=workout.endDate.isoformat(),
                duration=int(workout.duration or 0),
                distance=AEDistanceValue(
                    value=0.0,
                    unit="km",
                ),
                active_energy_burned=AEActiveEnergyValue(
                    value=summary_data.get("total_calories", 0.0),
                    unit="kcal",
                ),
                intensity=AEIntensityValue(
                    value=0.0,
                    unit="kcal/hr·kg",
                ),
                temperature=None,
                humidity=None,
                source=workout.sourceName,
                summary=AESummary(**summary_data),
            )
            workout_responses.append(workout_response)

        start_date_str = query_params.start_date or "1900-01-01T00:00:00Z"
        end_date_str = query_params.end_date or datetime.now().isoformat() + "Z"
        
        start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        duration_days = (end_date - start_date).days
        
        meta = AEWorkoutMeta(
            requested_at=datetime.now().isoformat() + "Z",
            filters=query_params.model_dump(exclude_none=True),
            result_count=total_count,
            date_range=AEDateRange(
                start=start_date_str,
                end=end_date_str,
                duration_days=duration_days,
            ),
        )

        return AEWorkoutListResponse(
            data=workout_responses,
            meta=meta,
        )


workout_service = WorkoutService(log=getLogger(__name__))
