from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.workout_repository import WorkoutRepository
from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.garmin.oauth import GarminOAuth
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class GarminStrategy(BaseProviderStrategy):
    """Garmin provider implementation."""

    def __init__(
        self,
        connection_repo: UserConnectionRepository,
        workout_repo: WorkoutRepository,
        user_repo, # Added user_repo as it is needed for OAuth template
    ):
        self.connection_repo = connection_repo
        self.workout_repo = workout_repo
        self.user_repo = user_repo
        self._oauth = GarminOAuth(user_repo, connection_repo)
        # self._workouts = GarminWorkouts(workout_repo, connection_repo) # To be implemented

    @property
    def name(self) -> str:
        return "garmin"

    @property
    def oauth(self) -> BaseOAuthTemplate | None:
        return self._oauth

    @property
    def workouts(self) -> BaseWorkoutsTemplate | None:
        # return self._workouts
        return None # Placeholder until implemented
