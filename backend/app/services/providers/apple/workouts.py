from datetime import datetime
from typing import Any
from uuid import UUID

from app.database import DbSession
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.event_record import EventRecordCreate
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.services.providers.apple.handlers.auto_export import AutoExportHandler
from app.services.providers.apple.handlers.base import AppleSourceHandler
from app.services.providers.apple.handlers.healthkit import HealthKitHandler
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class AppleWorkouts(BaseWorkoutsTemplate):
    """Apple Health implementation of the workouts template."""

    def __init__(
        self,
        workout_repo: EventRecordRepository,
        connection_repo: UserConnectionRepository,
    ):
        super().__init__(
            workout_repo,
            connection_repo,
            provider_name="apple",
            api_base_url="",
            oauth=None,  # type: ignore[arg-type]
        )
        self.handlers: dict[str, AppleSourceHandler] = {
            "auto_export": AutoExportHandler(),
            "healthkit": HealthKitHandler(),
        }

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Fetches workouts from Apple Health.

        Since Apple Health is primarily a local, push-based provider,
        this method might not be used for pulling data in the traditional sense.
        However, if there's a cloud sync mechanism, it could be implemented here.
        """
        return []

    def _normalize_workout(
        self,
        raw_workout: Any,
        user_id: UUID,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        """Apple payloads are normalized directly in handler classes."""
        raise NotImplementedError("Direct normalization not supported. Use process_push_data.")

    def process_payload(
        self,
        db: DbSession,
        user_id: UUID,
        payload: Any,
        source_type: str,
    ) -> None:
        """Processes data pushed from Apple Health sources.

        Args:
            db: Database session.
            user_id: User ID.
            payload: The raw data payload.
            source_type: The source of the data ('auto_export' or 'healthkit').
        """
        handler = self.handlers.get(source_type)
        if not handler:
            raise ValueError(f"Unknown Apple Health source: {source_type}")

        normalized_data = handler.normalize(payload)

        for record, detail in normalized_data:
            # We can reuse the internal save method from the template
            # Note: We need to ensure user_id is set on the record object
            record.user_id = user_id
            self._save_workout(db, record, detail)

    # Deprecated methods removed in favor of handlers
