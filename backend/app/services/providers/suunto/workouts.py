from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID, uuid4

from app.constants.workout_types.suunto import get_unified_workout_type
from app.database import DbSession
from app.models import DataSource
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordMetrics,
    SuuntoWorkoutJSON,
)
from app.services.event_record_service import event_record_service
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class SuuntoWorkouts(BaseWorkoutsTemplate):
    """Suunto implementation of workouts template."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.data_source_repo = DataSourceRepository(DataSource)

    def _get_suunto_headers(self) -> dict[str, str]:
        """Get Suunto-specific headers including subscription key."""
        headers = {}
        if self.oauth and hasattr(self.oauth, "credentials"):
            subscription_key = self.oauth.credentials.subscription_key
            if subscription_key:
                headers["Ocp-Apim-Subscription-Key"] = subscription_key
        return headers

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Get workouts from Suunto API."""
        # Suunto uses 'since' parameter
        since = int(start_date.timestamp())
        params = {
            "since": since,
            "limit": 100,
        }
        headers = self._get_suunto_headers()
        response = self._make_api_request(db, user_id, "/v3/workouts/", params=params, headers=headers)
        return response.get("payload", [])

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        """Get workouts from Suunto API with specific options."""
        since = kwargs.get("since", 0)
        limit = kwargs.get("limit", 50)
        offset = kwargs.get("offset", 0)
        filter_by_modification_time = kwargs.get("filter_by_modification_time", True)

        params = {
            "since": since,
            "limit": min(limit, 100),
            "offset": offset,
            "filter-by-modification-time": str(filter_by_modification_time).lower(),
        }

        # Suunto requires subscription key header
        headers = self._get_suunto_headers()

        return self._make_api_request(db, user_id, "/v3/workouts/", params=params, headers=headers)

    def get_workout_detail_from_api(self, db: DbSession, user_id: UUID, workout_id: str, **kwargs: Any) -> Any:
        """Get detailed workout data from Suunto API."""
        return self.get_workout_detail(db, user_id, workout_id)

    def _extract_dates(self, start_timestamp: int, end_timestamp: int) -> tuple[datetime, datetime]:
        """Extract start and end dates from timestamps."""
        start_date = datetime.fromtimestamp(start_timestamp / 1000)
        end_date = datetime.fromtimestamp(end_timestamp / 1000)
        return start_date, end_date

    def _build_metrics(self, raw_workout: SuuntoWorkoutJSON) -> EventRecordMetrics:
        """Build metrics from Suunto workout data.

        Note: For heart rate, use hrmax/workoutMaxHR (actual max during workout),
        NOT max (which is userMaxHR from settings).
        """
        hr_data = raw_workout.hrdata

        # Heart rate - use hrmax (actual workout max), not max (user's max HR from settings)
        heart_rate_avg = None
        heart_rate_max = None
        heart_rate_min = None

        if hr_data:
            # Average HR
            if hr_data.avg is not None:
                heart_rate_avg = Decimal(str(hr_data.avg))
            elif hr_data.workoutAvgHR is not None:
                heart_rate_avg = Decimal(str(hr_data.workoutAvgHR))

            # Max HR - use hrmax (actual workout max), fallback to workoutMaxHR
            if hr_data.hrmax is not None:
                heart_rate_max = Decimal(str(hr_data.hrmax))
            elif hr_data.workoutMaxHR is not None:
                heart_rate_max = Decimal(str(hr_data.workoutMaxHR))

            # Min HR
            if hr_data.min is not None:
                heart_rate_min = int(hr_data.min)

        # Steps
        steps_count = int(raw_workout.stepCount) if raw_workout.stepCount is not None else None

        energy_burned = (
            Decimal(str(raw_workout.energyConsumption)) if raw_workout.energyConsumption is not None else None
        )

        distance = Decimal(str(raw_workout.totalDistance)) if raw_workout.totalDistance is not None else None

        return {
            "heart_rate_min": heart_rate_min,
            "heart_rate_max": int(heart_rate_max) if heart_rate_max is not None else None,
            "heart_rate_avg": heart_rate_avg,
            "steps_count": steps_count,
            # Energy and distance
            "energy_burned": energy_burned,
            "distance": distance,
            # Speed (convert from m/s to km/h for display)
            "max_speed": Decimal(str(raw_workout.maxSpeed * 3.6)) if raw_workout.maxSpeed else None,
            "average_speed": Decimal(str(raw_workout.avgSpeed * 3.6)) if raw_workout.avgSpeed else None,
            # Power
            "max_watts": Decimal(str(raw_workout.maxPower)) if raw_workout.maxPower else None,
            "average_watts": Decimal(str(raw_workout.avgPower)) if raw_workout.avgPower else None,
            # Elevation
            "total_elevation_gain": Decimal(str(raw_workout.totalAscent)) if raw_workout.totalAscent else None,
            "elev_high": Decimal(str(raw_workout.maxAltitude)) if raw_workout.maxAltitude else None,
            "elev_low": Decimal(str(raw_workout.minAltitude)) if raw_workout.minAltitude else None,
        }

    def _normalize_workout(
        self,
        raw_workout: SuuntoWorkoutJSON,
        user_id: UUID,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        """Normalize Suunto workout to EventRecordCreate."""
        workout_id = uuid4()

        workout_type = get_unified_workout_type(raw_workout.activityId)

        start_date, end_date = self._extract_dates(raw_workout.startTime, raw_workout.stopTime)
        duration_seconds = int(raw_workout.totalTime)

        # Source name: prefer displayName, then name, fallback to "Suunto"
        if raw_workout.gear:
            source_name = raw_workout.gear.displayName or raw_workout.gear.name or "Suunto"
        else:
            source_name = "Suunto"

        # Device model: use display name or name from gear
        device_model = None
        if raw_workout.gear:
            device_model = raw_workout.gear.displayName or raw_workout.gear.name

        metrics = self._build_metrics(raw_workout)

        # Moving time (for now same as total time, Suunto may provide this separately)
        moving_time = duration_seconds

        workout_create = EventRecordCreate(
            category="workout",
            type=workout_type.value,
            source_name=source_name,
            device_model=device_model,
            duration_seconds=duration_seconds,
            start_datetime=start_date,
            end_datetime=end_date,
            id=workout_id,
            external_id=str(raw_workout.workoutId),
            source=self.provider_name,  # Provider name for mapping (e.g., "suunto")
            user_id=user_id,
        )

        # Add moving_time to metrics for workout_detail
        metrics["moving_time_seconds"] = moving_time

        workout_detail_create = EventRecordDetailCreate(
            record_id=workout_id,
            **metrics,
        )

        return workout_create, workout_detail_create

    def _build_bundles(
        self,
        raw: list[SuuntoWorkoutJSON],
        user_id: UUID,
    ) -> Iterable[tuple[EventRecordCreate, EventRecordDetailCreate]]:
        """Build event record payloads for Suunto workouts."""
        for raw_workout in raw:
            record, details = self._normalize_workout(raw_workout, user_id)
            yield record, details

    def load_data(
        self,
        db: DbSession,
        user_id: UUID,
        **kwargs: Any,
    ) -> bool:
        """Load data from Suunto API."""
        # Handle generic start_date/end_date
        start_date = kwargs.get("start_date")

        api_kwargs = kwargs.copy()

        # Convert start_date to 'since' timestamp
        if start_date:
            if isinstance(start_date, str):
                try:
                    start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                    api_kwargs["since"] = int(start_dt.timestamp())
                except (ValueError, AttributeError):
                    pass
            elif isinstance(start_date, datetime):
                api_kwargs["since"] = int(start_date.timestamp())

        # Set Suunto-specific defaults
        if "limit" not in api_kwargs:
            api_kwargs["limit"] = 100
        if "filter_by_modification_time" not in api_kwargs:
            api_kwargs["filter_by_modification_time"] = True

        response = self.get_workouts_from_api(db, user_id, **api_kwargs)
        workouts_data = response.get("payload", [])
        workouts = [SuuntoWorkoutJSON(**w) for w in workouts_data]

        for workout in workouts:
            # Save device/data source info if available
            if workout.gear:
                device_name = workout.gear.displayName or workout.gear.name
                self.data_source_repo.ensure_data_source(
                    db,
                    user_id=user_id,
                    device_model=device_name,
                    software_version=workout.gear.swVersion,
                    manufacturer="Suunto",
                    source=self.provider_name,
                )

        for record, details in self._build_bundles(workouts, user_id):
            created_record = event_record_service.create(db, record)
            detail_for_record = details.model_copy(update={"record_id": created_record.id})
            event_record_service.create_detail(db, detail_for_record)

        return True

    def get_workout_detail(
        self,
        db: DbSession,
        user_id: UUID,
        workout_key: str,
    ) -> dict:
        """Get detailed workout data from Suunto API."""
        headers = self._get_suunto_headers()
        return self._make_api_request(db, user_id, f"/v3/workouts/{workout_key}", headers=headers)

    def _process_single_workout(self, db: DbSession, user_id: UUID, raw_workout: Any) -> None:
        """Internal method to normalize and save a single workout.
        Overridden to save device info first and ensure Pydantic model conversion.
        """
        # Convert dict to Pydantic model if needed
        if isinstance(raw_workout, dict):
            raw_workout = SuuntoWorkoutJSON(**raw_workout)

        # Save device/data source info if available
        if raw_workout.gear:
            device_name = raw_workout.gear.displayName or raw_workout.gear.name
            self.data_source_repo.ensure_data_source(
                db,
                user_id=user_id,
                device_model=device_name,
                software_version=raw_workout.gear.swVersion,
                manufacturer="Suunto",
                source=self.provider_name,
            )

        super()._process_single_workout(db, user_id, raw_workout)
