from abc import ABC

from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workout_repository import WorkoutRepository
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class BaseProviderStrategy(ABC):
    """Abstract base class for all fitness data providers."""

    oauth: BaseOAuthTemplate | None = None
    workouts: BaseWorkoutsTemplate | None = None

    def __init__(self):
        self.user_repo = UserRepository()
        self.connection_repo = UserConnectionRepository()
        self.workout_repo = WorkoutRepository()

    @property
    def name(self) -> str:
        """Returns the unique name of the provider (e.g., 'garmin', 'suunto')."""
        raise NotImplementedError
