from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities, ProviderCoverage
from app.services.providers.google_health.coverage import HEALTH_SCORES, SLEEP_FIELDS, TIMESERIES, WORKOUT_FIELDS
from app.services.providers.google_health.data_247 import GoogleHealth247Data
from app.services.providers.google_health.oauth import GoogleOAuth
from app.services.providers.google_health.webhook_handler import GoogleWebhookHandler
from app.services.providers.google_health.webhook_service import GoogleWebhookService
from app.services.providers.google_health.workouts import GoogleHealthApiWorkouts


class GoogleHealthStrategy(BaseProviderStrategy):
    """Google Health API provider — the cloud OAuth path.

    Health Connect data pushed from Android devices is a separate provider; see
    ``app/services/providers/health_connect/strategy.py``.
    """

    def __init__(self):
        super().__init__()
        self.oauth = GoogleOAuth(
            user_repo=self.user_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
        )
        self.workouts = GoogleHealthApiWorkouts(self.workout_repo, self.connection_repo, self.oauth, self.api_base_url)
        self.data_247 = GoogleHealth247Data(self.oauth, self.connection_repo, self.api_base_url)
        self.webhooks = GoogleWebhookHandler(self.data_247, self.workouts)
        self.webhook_service = GoogleWebhookService()

    @property
    def name(self) -> str:
        return "google_health"

    @property
    def display_name(self) -> str:
        return "Google Health"

    @property
    def api_base_url(self) -> str:
        return "https://health.googleapis.com"

    @property
    def capabilities(self) -> ProviderCapabilities:
        # Cloud rollups polled over REST, with notify-only webhook pings (fetched via
        # REST); subscriber registration goes through the service account.
        return ProviderCapabilities(
            rest_pull=True,
            webhook_ping=True,
            webhook_registration_api=True,
        )

    @property
    def coverage(self) -> ProviderCoverage:
        return ProviderCoverage(
            timeseries=TIMESERIES,
            workout_fields=WORKOUT_FIELDS,
            sleep_fields=SLEEP_FIELDS,
            health_scores=HEALTH_SCORES,
        )
