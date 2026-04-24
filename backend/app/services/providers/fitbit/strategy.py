from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities
from app.services.providers.fitbit.oauth import FitbitOAuth
from app.services.providers.fitbit.workouts import FitbitWorkouts


class FitbitStrategy(BaseProviderStrategy):
    """Fitbit provider implementation."""

    def __init__(self) -> None:
        """Initialise OAuth and workouts handlers for Fitbit."""
        super().__init__()
        self.oauth = FitbitOAuth(
            user_repo=self.user_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
        )
        self.workouts = FitbitWorkouts(
            workout_repo=self.workout_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )

    @property
    def name(self) -> str:
        """Unique identifier for the provider (lowercase)."""
        return "fitbit"

    @property
    def api_base_url(self) -> str:
        """Base URL for the Fitbit Web API."""
        return "https://api.fitbit.com"

    @property
    def capabilities(self) -> ProviderCapabilities:
        # Fitbit Web API supports REST polling and a subscription-based webhook
        # system.  The webhook notification contains the user_id and collection
        # type; actual data must be fetched via the REST API.
        return ProviderCapabilities(rest_pull=True, webhook_ping=True)
