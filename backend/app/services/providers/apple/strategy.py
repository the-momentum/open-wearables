from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.workout_repository import WorkoutRepository
from app.services.providers.apple.workouts import AppleWorkouts
from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class AppleStrategy(BaseProviderStrategy):
    """Apple Health provider implementation."""

    def __init__(
        self,
        connection_repo: UserConnectionRepository,
        workout_repo: WorkoutRepository,
    ):
        self.connection_repo = connection_repo
        self.workout_repo = workout_repo
        self._workouts = AppleWorkouts(workout_repo, connection_repo)

    @property
    def name(self) -> str:
        return "apple"

    @property
    def oauth(self) -> BaseOAuthTemplate | None:
        """Apple Health does not use OAuth (local provider)."""
        return None

    @property
    def workouts(self) -> BaseWorkoutsTemplate | None:
        return self._workouts
