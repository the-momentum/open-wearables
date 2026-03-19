from datetime import datetime
from typing import Any
from uuid import UUID

from app.database import DbSession
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.event_record import EventRecordCreate
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class GoogleWorkouts(BaseWorkoutsTemplate):
    """Google Health Connect implementation of the workouts template.

    Google Health Connect is an SDK-based provider. Workouts are pushed from mobile devices
    via the SDK, not pulled from a cloud API.
    """

    def __init__(
        self,
        workout_repo: EventRecordRepository,
        connection_repo: UserConnectionRepository,
    ):
        super().__init__(
            workout_repo,
            connection_repo,
            provider_name="google_health_connect_sdk",
            api_base_url="",
            oauth=None,  # type: ignore[arg-type]
        )

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Fetches workouts from Google Health Connect.

        Since Google Health Connect is a push-based provider (SDK),
        this method is not used for pulling data.
        Workouts are received through the /sdk/users/{user_id}/sync/ endpoint.
        """
        return []

    def _normalize_workout(
        self,
        raw_workout: Any,
        user_id: UUID,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        """Google Health Connect payloads are normalized via the import service.

        Since Google Health Connect uses the same payload format as Apple HealthKit,
        data is processed through the import_service with Google Health Connect-specific
        provider/source settings.
        """
        raise NotImplementedError("Direct normalization not supported. Use SDK sync endpoint.")

    def _extract_dates(self, start_timestamp: Any, end_timestamp: Any) -> tuple[datetime, datetime]:
        """Google Health Connect uses datetime objects directly (same as Apple)."""
        if isinstance(start_timestamp, datetime) and isinstance(end_timestamp, datetime):
            return start_timestamp, end_timestamp
        raise ValueError("Google Health Connect expects datetime objects for timestamps")

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        """Google Health Connect does not support cloud API - data is push-only."""
        return []

    def get_workout_detail_from_api(self, db: DbSession, user_id: UUID, workout_id: str, **kwargs: Any) -> Any:
        """Google Health Connect does not support cloud API - data is push-only."""
        raise NotImplementedError("Google Health Connect does not support API-based workout detail fetching")
