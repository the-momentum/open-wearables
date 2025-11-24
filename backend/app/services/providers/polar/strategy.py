from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.workout_repository import WorkoutRepository
from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.polar.oauth import PolarOAuth
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class PolarStrategy(BaseProviderStrategy):
    """Polar provider implementation."""

    def __init__(
        self,
        connection_repo: UserConnectionRepository,
        workout_repo: WorkoutRepository,
        user_repo,
    ):
        self.connection_repo = connection_repo
        self.workout_repo = workout_repo
        self.user_repo = user_repo
        self._oauth = PolarOAuth(user_repo, connection_repo)

    @property
    def name(self) -> str:
        return "polar"

    @property
    def oauth(self) -> BaseOAuthTemplate | None:
        return self._oauth

    @property
    def workouts(self) -> BaseWorkoutsTemplate | None:
        return None # Placeholder
