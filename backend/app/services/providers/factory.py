from app.services.providers.apple.strategy import AppleStrategy
from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.garmin.strategy import GarminStrategy
from app.services.providers.polar.strategy import PolarStrategy
from app.services.providers.suunto.strategy import SuuntoStrategy
from app.services.providers.whoop.strategy import WhoopStrategy


class ProviderFactory:
    """Factory for creating provider instances."""

    def get_provider(self, provider_name: str) -> BaseProviderStrategy:
        match provider_name:
            case "apple":
                return AppleStrategy()
            case "garmin":
                return GarminStrategy()
            case "suunto":
                return SuuntoStrategy()
            case "polar":
                return PolarStrategy()
            case "whoop":
                return WhoopStrategy()
            case _:
                raise ValueError(f"Unknown provider: {provider_name}")
