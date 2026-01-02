from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.whoop.data_247 import Whoop247Data
from app.services.providers.whoop.oauth import WhoopOAuth


class WhoopStrategy(BaseProviderStrategy):
    """Whoop provider implementation."""

    def __init__(self):
        super().__init__()

        # Initialize OAuth component
        self.oauth = WhoopOAuth(
            user_repo=self.user_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
        )

        self.workouts = None

        # 247 data handler for sleep, recovery, activity samples
        self.data_247 = Whoop247Data(
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )

    @property
    def name(self) -> str:
        """Unique identifier for the provider (lowercase)."""
        return "whoop"

    @property
    def api_base_url(self) -> str:
        """Base URL for the provider's API."""
        return "https://api.prod.whoop.com/developer"
