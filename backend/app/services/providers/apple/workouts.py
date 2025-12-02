from datetime import datetime
from typing import Any
from uuid import UUID

from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.workout_repository import WorkoutRepository
from app.schemas.workout import WorkoutCreate
from app.services.providers.apple.handlers.auto_export import AutoExportHandler
from app.services.providers.apple.handlers.base import AppleSourceHandler
from app.services.providers.apple.handlers.healthkit import HealthKitHandler
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class AppleWorkouts(BaseWorkoutsTemplate):
    """Apple Health implementation of the workouts template."""

    def __init__(
        self,
        workout_repo: WorkoutRepository,
        connection_repo: UserConnectionRepository,
    ):
        super().__init__(
            workout_repo,
            connection_repo,
            provider_name="apple",
            api_base_url="",
            oauth=None,  # type: ignore[arg-type]
        )
        self.handlers: dict[str, AppleSourceHandler] = {
            "auto_export": AutoExportHandler(),
            "healthkit": HealthKitHandler(),
        }

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Fetches workouts from Apple Health.

        Since Apple Health is primarily a local, push-based provider,
        this method might not be used for pulling data in the traditional sense.
        However, if there's a cloud sync mechanism, it could be implemented here.
        """
        return []

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        """Apple Health doesn't support pulling workouts from API.

        Apple Health is push-based only - data comes from device uploads.
        """
        return []

    def get_workout_detail_from_api(self, db: DbSession, user_id: UUID, workout_id: str, **kwargs: Any) -> Any:
        """Apple Health doesn't support pulling workout details from API.

        Apple Health is push-based only - data comes from device uploads.
        """
        return None

    def normalize_workout(self, raw_workout: Any) -> WorkoutCreate:
        """Normalizes Apple Health workout data.

        This method is used by the Pull flow (get_workouts).
        Since Apple is Push-based, this might not be used directly unless
        get_workouts returns data.
        """
        raise NotImplementedError("Direct normalization not supported. Use process_push_data.")

    def process_payload(
        self,
        db: DbSession,
        user_id: UUID,
        payload: Any,
        source_type: str,
    ) -> None:
        """Processes data pushed from Apple Health sources.

        Args:
            db: Database session.
            user_id: User ID.
            payload: The raw data payload.
            source_type: The source of the data ('auto_export' or 'healthkit').
        """
        handler = self.handlers.get(source_type)
        if not handler:
            raise ValueError(f"Unknown Apple Health source: {source_type}")

        normalized_workouts = handler.normalize(payload)

        for workout in normalized_workouts:
            # We can reuse the internal save method from the template
            # Note: We need to ensure user_id is set on the workout object
            workout.user_id = user_id
            self._save_workout(db, workout)

    # Deprecated methods removed in favor of handlers
