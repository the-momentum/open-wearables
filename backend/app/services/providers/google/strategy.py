from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities, ProviderCoverage
from app.services.providers.google.coverage import HEALTH_SCORES, SLEEP_FIELDS, TIMESERIES, WORKOUT_FIELDS
from app.services.providers.google.health_api.data_247 import GoogleHealth247Data
from app.services.providers.google.health_api.oauth import GoogleOAuth
from app.services.providers.google.health_api.webhook_handler import GoogleWebhookHandler
from app.services.providers.google.health_api.webhook_service import GoogleWebhookService
from app.services.providers.google.health_api.workouts import GoogleHealthApiWorkouts


class GoogleStrategy(BaseProviderStrategy):
    """Google provider implementation.

    Google data arrives through two distinct paths:

    - ``sdk/``        — Health Connect data pushed from mobile devices via the SDK
                        (client_sdk, same payload format as Apple HealthKit).
    - ``health_api/`` — the Google cloud OAuth flow (Health/Fitness REST API) wired
                        via the OAuth handler so users can connect their Google account.

    Both share the single ``google`` provider identity (one connection per user)
    so source-string inference stays unambiguous.
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
        return "google"

    @property
    def display_name(self) -> str:
        return "Google Health"

    @property
    def api_base_url(self) -> str:
        return "https://health.googleapis.com"

    @property
    def capabilities(self) -> ProviderCapabilities:
        # Hybrid: Health Connect via the mobile SDK + the Google Health API cloud
        # rollups polled over REST. Health API delivers notify-only webhook pings
        # (fetched via REST); subscriber registration goes through the service account.
        return ProviderCapabilities(
            client_sdk=True,
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
