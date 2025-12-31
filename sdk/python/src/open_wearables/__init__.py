"""Open Wearables Python SDK - A typed, async-ready client for the Open Wearables API."""

from open_wearables.client import OpenWearables
from open_wearables.models import (
    Connection,
    User,
    Workout,
    WorkoutStatistic,
)

__version__ = "0.1.0"
__all__ = [
    "OpenWearables",
    "User",
    "Workout",
    "WorkoutStatistic",
    "Connection",
]
