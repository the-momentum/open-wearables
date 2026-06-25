from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities, ProviderCoverage
from app.services.providers.google.coverage import HEALTH_SCORES, SLEEP_FIELDS, TIMESERIES, WORKOUT_FIELDS
from app.services.providers.google.health_api.oauth import GoogleOAuth
from app.services.providers.google.sdk.workouts import GoogleWorkouts


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

    @property
    def capabilities(self) -> ProviderCapabilities:
        # Google Health Connect data arrives exclusively via the mobile SDK (no cloud API).
        return ProviderCapabilities(client_sdk=True)

    @property
    def coverage(self) -> ProviderCoverage:
        return ProviderCoverage(
            timeseries=TIMESERIES,
            workout_fields=WORKOUT_FIELDS,
            sleep_fields=SLEEP_FIELDS,
            health_scores=HEALTH_SCORES,
        )
