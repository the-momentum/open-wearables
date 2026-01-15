"""Ultrahuman Ring Air 24/7 data implementation for sleep, recovery, and activity samples."""

from contextlib import suppress
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.database import DbSession
from app.models import EventRecord, ExternalDeviceMapping
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.repositories.external_mapping_repository import ExternalMappingRepository
from app.schemas import EventRecordCreate
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.services.event_record_service import event_record_service
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate


class Ultrahuman247Data(Base247DataTemplate):
    """Ultrahuman Ring Air implementation for 24/7 data (sleep, recovery, activity)."""

    def __init__(
        self,
        provider_name: str,
        api_base_url: str,
        oauth: BaseOAuthTemplate,
    ):
        super().__init__(provider_name, api_base_url, oauth)
        self.event_record_repo = EventRecordRepository(EventRecord)
        self.mapping_repo = ExternalMappingRepository(ExternalDeviceMapping)
        self.connection_repo = UserConnectionRepository()

    def _make_api_request(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make authenticated request to Ultrahuman API."""
        return make_authenticated_request(
            db=db,
            user_id=user_id,
            connection_repo=self.connection_repo,
            oauth=self.oauth,
            api_base_url=self.api_base_url,
            provider_name=self.provider_name,
            endpoint=endpoint,
            method="GET",
            params=params,
            headers=headers,
        )

    # -------------------------------------------------------------------------
    # Sleep Data
    # -------------------------------------------------------------------------

    def get_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch sleep data from Ultrahuman API.

        Ultrahuman provides date-based sleep data in YYYY-MM-DD format.
        """
        all_sleep_data = []
        current_date = start_time.date()
        end_date = end_time.date()

        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            try:
                response = self._make_api_request(
                    db,
                    user_id,
                    "/user_data/sleep",
                    params={"date": date_str},
                )
                if response:
                    # Add date to response for normalization
                    response["date"] = date_str
                    all_sleep_data.append(response)
            except Exception as e:
                self.logger.warning(f"Failed to fetch sleep data for {date_str}: {e}")

            current_date = datetime.fromordinal(current_date.toordinal() + 1).date()

        return all_sleep_data

    def normalize_sleep(
        self,
        raw_sleep: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize Ultrahuman sleep data to our schema.

        Ultrahuman provides:
        - total_sleep_duration (seconds)
        - deep_sleep_duration (seconds)
        - rem_sleep_duration (seconds)
        - light_sleep_duration (seconds)
        - sleep_efficiency (percentage)
        - bed_time (ISO timestamp)
        - wake_time (ISO timestamp)
        """
        # Extract basic fields
        date_str = raw_sleep.get("date")
        bed_time = raw_sleep.get("bed_time")
        wake_time = raw_sleep.get("wake_time")

        # Parse timestamps
        start_dt = None
        end_dt = None
        if bed_time:
            with suppress(ValueError, AttributeError):
                start_dt = datetime.fromisoformat(bed_time.replace("Z", "+00:00"))
        if wake_time:
            with suppress(ValueError, AttributeError):
                end_dt = datetime.fromisoformat(wake_time.replace("Z", "+00:00"))

        # Durations are typically in seconds from Ultrahuman
        total_seconds = raw_sleep.get("total_sleep_duration", 0) or 0
        deep_seconds = raw_sleep.get("deep_sleep_duration", 0) or 0
        rem_seconds = raw_sleep.get("rem_sleep_duration", 0) or 0
        light_seconds = raw_sleep.get("light_sleep_duration", 0) or 0

        # Calculate awake time (time in bed - total sleep)
        time_in_bed_seconds = 0
        if start_dt and end_dt:
            time_in_bed_seconds = int((end_dt - start_dt).total_seconds())
            awake_seconds = max(0, time_in_bed_seconds - total_seconds)
        else:
            awake_seconds = 0

        # Efficiency percentage
        efficiency = raw_sleep.get("sleep_efficiency")

        # Generate UUID for internal ID
        internal_id = uuid4()

        return {
            "id": internal_id,
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": bed_time or wake_time,
            "start_time": bed_time,
            "end_time": wake_time,
            "duration_seconds": time_in_bed_seconds if start_dt and end_dt else total_seconds,
            "efficiency_percent": float(efficiency) if efficiency is not None else None,
            "is_nap": raw_sleep.get("is_nap", False),
            "stages": {
                "deep_seconds": int(deep_seconds),
                "light_seconds": int(light_seconds),
                "rem_seconds": int(rem_seconds),
                "awake_seconds": int(awake_seconds),
            },
            "ultrahuman_date": date_str,
            "raw": raw_sleep,
        }

    def save_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_sleep: dict[str, Any],
    ) -> None:
        """Save normalized sleep data to database as EventRecord with SleepDetails."""
        sleep_id = normalized_sleep["id"]

        # Parse start and end times
        start_dt = None
        end_dt = None
        if normalized_sleep.get("start_time"):
            start_time = normalized_sleep["start_time"]
            if isinstance(start_time, str):
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            elif isinstance(start_time, datetime):
                start_dt = start_time

        if normalized_sleep.get("end_time"):
            end_time = normalized_sleep["end_time"]
            if isinstance(end_time, str):
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            elif isinstance(end_time, datetime):
                end_dt = end_time

        if not start_dt or not end_dt:
            self.logger.warning(f"Skipping sleep record {sleep_id}: missing start/end time")
            return

        # Create EventRecord for sleep
        record = EventRecordCreate(
            id=sleep_id,
            category="sleep",
            type="sleep_session",
            source_name="Ultrahuman Ring Air",
            device_id=None,
            external_device_mapping_id=None,
            duration_seconds=normalized_sleep.get("duration_seconds"),
            start_datetime=start_dt,
            end_datetime=end_dt,
            external_id=normalized_sleep.get("ultrahuman_date"),
            provider_name=self.provider_name,
            user_id=user_id,
        )

        # Create detail with sleep-specific fields
        stages = normalized_sleep.get("stages", {})
        total_sleep_seconds = (
            stages.get("deep_seconds", 0) + stages.get("light_seconds", 0) + stages.get("rem_seconds", 0)
        )
        total_sleep_minutes = total_sleep_seconds // 60
        time_in_bed_minutes = normalized_sleep.get("duration_seconds", 0) // 60

        detail = EventRecordDetailCreate(
            record_id=sleep_id,
            sleep_total_duration_minutes=total_sleep_minutes,
            sleep_time_in_bed_minutes=time_in_bed_minutes,
            sleep_efficiency_score=Decimal(str(normalized_sleep.get("efficiency_percent", 0)))
            if normalized_sleep.get("efficiency_percent") is not None
            else None,
            sleep_deep_minutes=stages.get("deep_seconds", 0) // 60,
            sleep_light_minutes=stages.get("light_seconds", 0) // 60,
            sleep_rem_minutes=stages.get("rem_seconds", 0) // 60,
            sleep_awake_minutes=stages.get("awake_seconds", 0) // 60,
            is_nap=normalized_sleep.get("is_nap", False),
        )

        try:
            created_record = event_record_service.create(db, record)
            detail.record_id = created_record.id
            event_record_service.create_detail(db, detail, detail_type="sleep")
        except Exception as e:
            self.logger.error(f"Error saving sleep record {sleep_id}: {e}")

    # -------------------------------------------------------------------------
    # Recovery Data
    # -------------------------------------------------------------------------

    def get_recovery_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch recovery data from Ultrahuman API.

        Ultrahuman provides recovery metrics including:
        - recovery_index (0-100)
        - movement_index (0-100)
        - metabolic_score (0-100)
        """
        all_recovery_data = []
        current_date = start_time.date()
        end_date = end_time.date()

        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            try:
                response = self._make_api_request(
                    db,
                    user_id,
                    "/user_data/recovery",
                    params={"date": date_str},
                )
                if response:
                    response["date"] = date_str
                    all_recovery_data.append(response)
            except Exception as e:
                self.logger.warning(f"Failed to fetch recovery data for {date_str}: {e}")

            current_date = datetime.fromordinal(current_date.toordinal() + 1).date()

        return all_recovery_data

    def normalize_recovery(
        self,
        raw_recovery: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize Ultrahuman recovery data to our schema."""
        date_str = raw_recovery.get("date")

        return {
            "id": uuid4(),
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": date_str,
            "date": date_str,
            "recovery_index": raw_recovery.get("recovery_index"),
            "movement_index": raw_recovery.get("movement_index"),
            "metabolic_score": raw_recovery.get("metabolic_score"),
            "raw": raw_recovery,
        }

    # -------------------------------------------------------------------------
    # Activity Samples (HR, HRV, Temperature, Steps)
    # -------------------------------------------------------------------------

    def get_activity_samples(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch activity samples from Ultrahuman API.

        Returns heart rate, HRV, temperature, and steps data.
        """
        all_samples = []
        current_date = start_time.date()
        end_date = end_time.date()

        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            try:
                response = self._make_api_request(
                    db,
                    user_id,
                    "/user_data/metrics",
                    params={"date": date_str},
                )
                if response:
                    response["date"] = date_str
                    all_samples.append(response)
            except Exception as e:
                self.logger.warning(f"Failed to fetch metrics for {date_str}: {e}")

            current_date = datetime.fromordinal(current_date.toordinal() + 1).date()

        return all_samples

    def normalize_activity_samples(
        self,
        raw_samples: list[dict[str, Any]],
        user_id: UUID,
    ) -> dict[str, list[dict[str, Any]]]:
        """Normalize activity samples into categorized data.

        Returns dict with keys: 'heart_rate', 'hrv', 'temperature', 'steps'.
        """
        result = {
            "heart_rate": [],
            "hrv": [],
            "temperature": [],
            "steps": [],
        }

        for sample in raw_samples:
            date_str = sample.get("date")
            recorded_at = datetime.fromisoformat(date_str) if date_str else datetime.now(timezone.utc)

            # Heart rate samples
            hr_data = sample.get("heart_rate", [])
            if isinstance(hr_data, list):
                for hr in hr_data:
                    result["heart_rate"].append(
                        {
                            "id": uuid4(),
                            "user_id": user_id,
                            "provider": self.provider_name,
                            "recorded_at": recorded_at.isoformat(),
                            "value": hr.get("value"),
                            "unit": "bpm",
                        }
                    )

            # HRV samples
            hrv_data = sample.get("hrv", [])
            if isinstance(hrv_data, list):
                for hrv in hrv_data:
                    result["hrv"].append(
                        {
                            "id": uuid4(),
                            "user_id": user_id,
                            "provider": self.provider_name,
                            "recorded_at": recorded_at.isoformat(),
                            "value": hrv.get("value"),
                            "unit": "ms",
                        }
                    )

            # Temperature samples
            temp_data = sample.get("temperature", [])
            if isinstance(temp_data, list):
                for temp in temp_data:
                    result["temperature"].append(
                        {
                            "id": uuid4(),
                            "user_id": user_id,
                            "provider": self.provider_name,
                            "recorded_at": recorded_at.isoformat(),
                            "value": temp.get("value"),
                            "unit": "celsius",
                        }
                    )

            # Steps
            steps = sample.get("steps")
            if steps is not None:
                result["steps"].append(
                    {
                        "id": uuid4(),
                        "user_id": user_id,
                        "provider": self.provider_name,
                        "recorded_at": recorded_at.isoformat(),
                        "value": steps,
                        "unit": "count",
                    }
                )

        return result

    # -------------------------------------------------------------------------
    # Daily Activity Statistics
    # -------------------------------------------------------------------------

    def get_daily_activity_statistics(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch aggregated daily activity statistics."""
        return []

    def normalize_daily_activity(
        self,
        raw_stats: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize daily activity statistics to our schema."""
        return {}

    # -------------------------------------------------------------------------
    # Combined Load
    # -------------------------------------------------------------------------

    def load_and_save_sleep(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Load sleep data from API and save to database."""
        raw_data = self.get_sleep_data(db, user_id, start_time, end_time)
        count = 0
        for item in raw_data:
            try:
                normalized = self.normalize_sleep(item, user_id)
                self.save_sleep_data(db, user_id, normalized)
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to save sleep data: {e}")
        return count

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
    ) -> dict[str, int]:
        """Load and save all 247 data types (activity samples).

        Ultrahuman provides ring metrics (activity samples) through /user_data/metrics endpoint.
        Sleep and recovery data are not provided as separate endpoints.
        """
        from datetime import timedelta

        # Handle date defaults (last 30 days if not specified)
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        # Set defaults if None
        if end_time is None:
            end_time = datetime.now(timezone.utc)
        if start_time is None:
            start_time = end_time - timedelta(days=30)

        results = {
            "sleep_sessions_synced": 0,
            "activity_samples": 0,
        }

        try:
            results["sleep_sessions_synced"] = self.load_and_save_sleep(db, user_id, start_time, end_time)
        except Exception as e:
            self.logger.error(f"Failed to sync sleep data: {e}")

        try:
            activity_result = self.process_activity_samples(db, user_id, start_time, end_time)
            # Count total samples
            total_samples = sum(len(v) for v in activity_result.values())
            results["activity_samples"] = total_samples
        except Exception as e:
            self.logger.error(f"Failed to sync activity samples: {e}")

        return results
