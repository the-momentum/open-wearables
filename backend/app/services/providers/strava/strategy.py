from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities
from app.services.providers.strava.oauth import StravaOAuth
from app.services.providers.strava.workouts import StravaWorkouts


class StravaStrategy(BaseProviderStrategy):
    """Strava provider implementation."""

    def __init__(self):
        super().__init__()

        # Initialize OAuth component
        self.oauth = StravaOAuth(
            user_repo=self.user_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
        )

        # Initialize workouts component
        self.workouts = StravaWorkouts(
            workout_repo=self.workout_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )

        # Strava has no continuous monitoring data (no sleep, HRV, daily summaries)
        self.data_247 = None

    @property
    def name(self) -> str:
        """Unique identifier for the provider (lowercase)."""
        return "strava"

    @property
    def api_base_url(self) -> str:
        """Base URL for the provider's API."""
        return "https://www.strava.com/api/v3"

    @property
    def capabilities(self) -> ProviderCapabilities:
        # Strava push subscriptions deliver an `aspect_type=create` event
        # for every new activity within seconds of upload-finalisation.
        # The webhook handler at
        # ``backend/app/services/providers/strava/handlers/webhook_helpers.py``
        # then fetches the full activity via GET ``/activities/{id}`` and
        # persists it through the same path as a REST pull.
        #
        # REST polling (``rest_pull``) is kept on for historical backfills
        # and as a safety net against webhook delivery failures.
        #
        # ``webhook_ping=True`` only advertises the capability; deployments
        # that haven't created a Strava push subscription yet remain on the
        # rest_pull path with no behaviour change.  See the route at
        # ``backend/app/api/routes/v1/strava_webhooks.py`` and the
        # subscription-creation flow in
        # ``handlers/webhook_helpers.py:handle_webhook_verification`` for
        # operator setup.
        return ProviderCapabilities(rest_pull=True, webhook_ping=True)
