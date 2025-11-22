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
        """Template method to fetch, normalize, and save workouts.

        Args:
            db: Database session.
            user_id: The ID of the user.
            start_date: Start of the date range.
            end_date: End of the date range.
        """
        raw_workouts = self.get_workouts(db, user_id, start_date, end_date)
        for raw in raw_workouts:
            workout_data = self.normalize_workout(raw)
            # Ensure user_id is set correctly
            workout_data.user_id = user_id
            
            # TODO: Add logic to check if workout already exists to avoid duplicates
            # For now, we just create it.
            self.workout_repo.create(db, workout_data)
