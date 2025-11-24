from typing import Any

from app.schemas.workout import WorkoutCreate
from app.services.providers.apple.handlers.base import AppleSourceHandler


class AutoExportHandler(AppleSourceHandler):
    """Handler for Apple Health 'Auto Export' app data."""

    def normalize(self, data: Any) -> list[WorkoutCreate]:
        # TODO: Implement Auto Export specific normalization logic
        # This is where we parse the JSON structure from Auto Export
        return []
