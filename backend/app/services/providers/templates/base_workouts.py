import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.workout_repository import WorkoutRepository
from app.schemas.workout import WorkoutCreate
from app.services.providers.templates import BaseOAuthTemplate


class BaseWorkoutsTemplate(ABC):
    """Base template for fetching and processing workouts."""

    def __init__(
        self,
        workout_repo: WorkoutRepository,
        connection_repo: UserConnectionRepository,
        oauth: BaseOAuthTemplate,
    ):
        self.workout_repo = workout_repo
        self.connection_repo = connection_repo
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
        workout_data = self.normalize_workout(raw_workout)
        workout_data.user_id = user_id
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
    ) -> Any:
        """Make authenticated request to vendor API.

        Args:
            db: Database session
            user_id: User ID
            endpoint: API endpoint path
            method: HTTP method (default: GET)
            params: Query parameters
            headers: Additional headers

        Returns:
            Any: API response JSON

        Raises:
            HTTPException: If API request fails
        """
        return self.oauth.make_api_request(db, user_id, endpoint, method, params, headers)
