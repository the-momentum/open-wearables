from app.schemas.enums import ProviderName
from app.services.providers.apple.strategy import AppleStrategy
from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.fitbit.strategy import FitbitStrategy
from app.services.providers.garmin.strategy import GarminStrategy
from app.services.providers.google_health.strategy import GoogleHealthStrategy
from app.services.providers.health_connect.strategy import HealthConnectStrategy
from app.services.providers.hevy.strategy import HevyStrategy
from app.services.providers.oura.strategy import OuraStrategy
from app.services.providers.polar.strategy import PolarStrategy
from app.services.providers.samsung.strategy import SamsungStrategy
from app.services.providers.sensorbio.strategy import SensorBioStrategy
from app.services.providers.strava.strategy import StravaStrategy
from app.services.providers.suunto.strategy import SuuntoStrategy
from app.services.providers.ultrahuman.strategy import UltrahumanStrategy
from app.services.providers.whoop.strategy import WhoopStrategy
from app.services.providers.withings.strategy import WithingsStrategy


class ProviderFactory:
    """Factory for creating provider instances."""

    def get_provider(self, provider_name: str) -> BaseProviderStrategy:
        match provider_name:
            case ProviderName.APPLE.value:
                return AppleStrategy()
            case ProviderName.SAMSUNG.value:
                return SamsungStrategy()
            case ProviderName.HEALTH_CONNECT.value:
                return HealthConnectStrategy()
            case ProviderName.GOOGLE_HEALTH.value:
                return GoogleHealthStrategy()
            case ProviderName.GARMIN.value:
                return GarminStrategy()
            case ProviderName.SENSORBIO.value:
                return SensorBioStrategy()
            case ProviderName.HEVY.value:
                return HevyStrategy()
            case ProviderName.SUUNTO.value:
                return SuuntoStrategy()
            case ProviderName.POLAR.value:
                return PolarStrategy()
            case ProviderName.WHOOP.value:
                return WhoopStrategy()

            case ProviderName.OURA.value:
                return OuraStrategy()
            case ProviderName.STRAVA.value:
                return StravaStrategy()
            case ProviderName.FITBIT.value:
                return FitbitStrategy()
            case ProviderName.ULTRAHUMAN.value:
                return UltrahumanStrategy()
            case ProviderName.WITHINGS.value:
                return WithingsStrategy()
            case _:
                raise ValueError(f"Unknown provider: {provider_name}")
