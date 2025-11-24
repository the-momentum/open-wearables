from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.workout_repository import WorkoutRepository
from app.schemas.workout import WorkoutCreate


class BaseWorkoutsTemplate(ABC):
    """Base template for fetching and processing workouts.

    This class implements the Template Method pattern for workout operations.
    It defines the workflow for fetching, normalizing, and saving workouts,
    allowing subclasses to focus on provider-specific API calls and data mapping.
    """

    def __init__(
        self,
        workout_repo: WorkoutRepository,
        connection_repo: UserConnectionRepository,
    ):
        self.workout_repo = workout_repo
        self.connection_repo = connection_repo

    @abstractmethod
    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Fetches workouts from the provider API.

        Args:
            db: Database session.
            user_id: The ID of the user.
            start_date: Start of the date range.
            end_date: End of the date range.

        Returns:
            list[Any]: A list of raw workout objects from the provider.
        """
        pass

    @abstractmethod
    def normalize_workout(self, raw_workout: Any) -> WorkoutCreate:
        """Converts a provider-specific workout object into a standardized WorkoutCreate schema.

        Args:
            raw_workout: The raw workout object from the provider.

        Returns:
            WorkoutCreate: The standardized workout data.
        """
        pass

    def process_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> None:
        """Template method to fetch, normalize, and save workouts (Pull flow).

        Args:
            db: Database session.
            user_id: The ID of the user.
            start_date: Start of the date range.
            end_date: End of the date range.
        """
        # 1. Fetch raw data
        raw_workouts = self._fetch_workouts(db, user_id, start_date, end_date)

        # 2. Process each workout
        for raw in raw_workouts:
            self._process_single_workout(db, user_id, raw)

    def process_payload(self, db: DbSession, user_id: UUID, payload: Any, source_type: str) -> None:
        """Template method to process a pushed payload (Push flow).

        Args:
            db: Database session.
            user_id: The ID of the user.
            payload: The raw data payload (e.g. from webhook or file upload).
            source_type: Identifier for the source (e.g. 'auto_export', 'healthkit', 'garmin_push').
        """
        # This method can be overridden or extended by subclasses to handle specific payload structures
        # For example, a payload might contain a list of workouts or a single workout

        # Default implementation assumes payload might be a list or single item,
        # but subclasses should probably override this to parse the specific format
        # and then call _process_single_workout.
        pass

    def _fetch_workouts(self, db: DbSession, user_id: UUID, start_date: datetime, end_date: datetime) -> list[Any]:
        """Internal method to fetch workouts. Delegates to abstract get_workouts."""
        return self.get_workouts(db, user_id, start_date, end_date)

    def _process_single_workout(self, db: DbSession, user_id: UUID, raw_workout: Any) -> None:
        """Internal method to normalize and save a single workout."""
        workout_data = self.normalize_workout(raw_workout)
        workout_data.user_id = user_id
        self._save_workout(db, workout_data)

    def _save_workout(self, db: DbSession, workout_data: WorkoutCreate) -> None:
        """Internal method to save the workout to the database."""
        # TODO: Add logic to check if workout already exists to avoid duplicates
        self.workout_repo.create(db, workout_data)
