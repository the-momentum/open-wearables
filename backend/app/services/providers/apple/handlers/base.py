from abc import ABC, abstractmethod
from typing import Any

from app.schemas.event_record import EventRecordCreate
from app.schemas.event_record_detail import EventRecordDetailCreate


class AppleSourceHandler(ABC):
    """Base interface for Apple Health data source handlers."""

    @abstractmethod
    def normalize(self, data: Any) -> list[tuple[EventRecordCreate, EventRecordDetailCreate]]:
        """Normalizes raw data from a specific Apple source into unified event records.

        Args:
            data: The raw data payload.

        Returns:
            List of (EventRecordCreate, EventRecordDetailCreate) tuples.
        """
        pass
