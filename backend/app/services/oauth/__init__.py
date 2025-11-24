"""OAuth strategy classes for different providers."""

from .base_oauth_strategy import BaseOAuthStrategy
from .garmin_oauth_strategy import GarminOAuthStrategy
from .standard_oauth_strategy import PolarOAuthStrategy, StandardOAuthStrategy, SuuntoOAuthStrategy

__all__ = [
    "BaseOAuthStrategy",
    "GarminOAuthStrategy",
    "SuuntoOAuthStrategy",
    "PolarOAuthStrategy",
    "StandardOAuthStrategy",
]
