from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.google.workouts import GoogleWorkouts


class GoogleStrategy(BaseProviderStrategy):
    """Google Health Connect provider implementation.

    Google Health Connect is an SDK-based provider (similar to Apple Health) without
    cloud OAuth API. Data is pushed from mobile devices via the SDK.
    """

    def __init__(self):
        super().__init__()
        self.workouts = GoogleWorkouts(self.workout_repo, self.connection_repo)

    @property
    def name(self) -> str:
        return "google"

    @property
    def display_name(self) -> str:
        return "Google Health Connect"

    @property
    def api_base_url(self) -> str:
        return ""  # Google Health Connect doesn't have a cloud API
