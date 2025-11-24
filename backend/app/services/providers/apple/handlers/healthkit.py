from typing import Any

from app.schemas.workout import WorkoutCreate
from app.services.providers.apple.handlers.base import AppleSourceHandler


class HealthKitHandler(AppleSourceHandler):
    """Handler for direct HealthKit export data."""

    def normalize(self, data: Any) -> list[WorkoutCreate]:
        # TODO: Implement HealthKit specific normalization logic
        # This is where we parse the payload from our HealthKit integration
        return []
