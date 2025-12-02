import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.workout_repository import WorkoutRepository
from app.schemas.workout import WorkoutCreate
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.templates.base_oauth import BaseOAuthTemplate


class BaseWorkoutsTemplate(ABC):
    """Base template for fetching and processing workouts."""

    def __init__(
        self,
        workout_repo: WorkoutRepository,
        connection_repo: UserConnectionRepository,
        provider_name: str,
        api_base_url: str,
        oauth: "BaseOAuthTemplate",
    ):
        self.workout_repo = workout_repo
        self.connection_repo = connection_repo
        self.provider_name = provider_name
        self.api_base_url = api_base_url
        self.oauth = oauth
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Fetches workouts from the provider API."""
        pass

    @abstractmethod
    def _normalize_workout(self, raw_workout: Any, user_id: UUID) -> WorkoutCreate:
        """Converts a provider-specific workout object into a standardized WorkoutCreate schema.

        Args:
            raw_workout: The raw workout object from the provider.
            user_id: The user ID to associate with the workout.

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
        """Template method to fetch, normalize, and save workouts (Pull flow)."""
        raw_workouts = self.get_workouts(db, user_id, start_date, end_date)

        for raw in raw_workouts:
            self._process_single_workout(db, user_id, raw)

    @abstractmethod
    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        """Fetch workouts from API with flexible parameters (for API endpoint)."""
        pass

    @abstractmethod
    def get_workout_detail_from_api(self, db: DbSession, user_id: UUID, workout_id: str, **kwargs: Any) -> Any:
        """Fetch detailed workout from API (for API endpoint)."""
        pass

    def load_data(self, db: DbSession, user_id: UUID, **kwargs: Any) -> bool:
        """Load data from provider API."""
        pass

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

    def _process_single_workout(self, db: DbSession, user_id: UUID, raw_workout: Any) -> None:
        """Internal method to normalize and save a single workout."""
        workout_data = self._normalize_workout(raw_workout, user_id)
        # workout_data.user_id = user_id # Already set in _normalize_workout
        self._save_workout(db, workout_data)

    def _save_workout(self, db: DbSession, workout_data: WorkoutCreate) -> None:
        """Internal method to save the workout to the database."""
        # TODO: Add logic to check if workout already exists to avoid duplicates
        self.workout_repo.create(db, workout_data)

    def _make_api_request(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> Any:
        """Make authenticated request to vendor API."""
        return make_authenticated_request(
            db=db,
            user_id=user_id,
            connection_repo=self.connection_repo,
            oauth=self.oauth,
            api_base_url=self.api_base_url,
            provider_name=self.provider_name,
            endpoint=endpoint,
            method=method,
            params=params,
            headers=headers,
            json_data=json_data,
        )
