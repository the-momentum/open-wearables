from abc import ABC, abstractmethod
from typing import Any

from app.schemas.workout import WorkoutCreate


class AppleSourceHandler(ABC):
    """Base interface for Apple Health data source handlers."""

    @abstractmethod
    def normalize(self, data: Any) -> list[WorkoutCreate]:
        """Normalizes raw data from a specific Apple source into a list of WorkoutCreate objects.

        Args:
            data: The raw data payload.

        Returns:
            list[WorkoutCreate]: A list of normalized workout objects.
        """
        pass
