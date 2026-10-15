from enum import Enum


class ProviderName(str, Enum):
    """Supported data providers."""

    APPLE = "apple"
    SAMSUNG = "samsung"
    GARMIN = "garmin"
    HEALTH_CONNECT = "health_connect"
    GOOGLE_HEALTH = "google_health"
    POLAR = "polar"
    SUUNTO = "suunto"
    WHOOP = "whoop"
    STRAVA = "strava"
    OURA = "oura"
    FITBIT = "fitbit"
    ULTRAHUMAN = "ultrahuman"
    SENSORBIO = "sensorbio"
    WITHINGS = "withings"
    UNKNOWN = "unknown"
    INTERNAL = "internal"

    @classmethod
    def from_source_string(cls, source: str | None) -> "ProviderName":
        """Infer provider from a source string by checking if provider name appears in it.

        Args:
            source: Source string (e.g., "apple_health_sdk", "Garmin Connect")

        Returns:
            Matching ProviderName or UNKNOWN if no match found
        """
        if not source:
            return cls.UNKNOWN

        source_lower = source.lower()
        # Check each provider (except UNKNOWN) to see if it appears in the source string
        for provider in cls:
            if provider in (cls.UNKNOWN, cls.INTERNAL):
                continue
            if provider.value in source_lower:
                return provider

        return cls.UNKNOWN


# Default order for a fresh deployment. Covers every provider a user can connect;
# UNKNOWN and INTERNAL are deliberately absent because they are not configurable.
DEFAULT_PROVIDER_PRIORITY: dict[ProviderName, int] = {
    ProviderName.APPLE: 1,
    ProviderName.GARMIN: 2,
    ProviderName.POLAR: 3,
    ProviderName.SUUNTO: 4,
    ProviderName.WHOOP: 5,
    ProviderName.FITBIT: 6,
    ProviderName.GOOGLE_HEALTH: 7,
    ProviderName.HEALTH_CONNECT: 8,
    ProviderName.OURA: 9,
    ProviderName.SAMSUNG: 10,
    ProviderName.SENSORBIO: 11,
    ProviderName.STRAVA: 12,
    ProviderName.ULTRAHUMAN: 13,
    ProviderName.WITHINGS: 14,
}
