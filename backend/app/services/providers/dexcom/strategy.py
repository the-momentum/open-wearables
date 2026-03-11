from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.dexcom.data_247 import Dexcom247Data
from app.services.providers.dexcom.oauth import DexcomOAuth


class DexcomStrategy(BaseProviderStrategy):
    """Dexcom CGM provider implementation."""

    def __init__(self):
        super().__init__()

        # Initialize OAuth component
        self.oauth = DexcomOAuth(
            user_repo=self.user_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
        )

        # 247 data handler for EGV glucose readings
        self.data_247 = Dexcom247Data(
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )

    @property
    def name(self) -> str:
        """Unique identifier for the provider (lowercase)."""
        return "dexcom"

    @property
    def api_base_url(self) -> str:
        """Base URL for the Dexcom API."""
        return "https://api.dexcom.com"

    @property
    def display_name(self) -> str:
        """Human-readable display name."""
        return "Dexcom"
