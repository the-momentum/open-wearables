"""Ultrahuman Ring Air 24/7 data implementation for sleep, recovery, and activity samples."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.database import DbSession
from app.models import DataPointSeries, EventRecord, ExternalDeviceMapping
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.repositories.data_point_series_repository import DataPointSeriesRepository
from app.repositories.external_mapping_repository import ExternalMappingRepository
from app.schemas import EventRecordCreate, TimeSeriesSampleCreate
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.schemas.series_types import SeriesType
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
        self.data_point_repo = DataPointSeriesRepository(DataPointSeries)

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

    def _fetch_daily_metrics(
        self,
        db: DbSession,
        user_id: UUID,
        date: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch all metrics for a specific day from Ultrahuman API."""
        date_str = date.strftime("%Y-%m-%d")
        try:
            response = self._make_api_request(
                db,
                user_id,
                "/user_data/metrics",
                params={"date": date_str},
            )
            if response and "data" in response and "metric_data" in response["data"]:
                # Add date to each metric item for reference
                metrics = response["data"]["metric_data"]
                for item in metrics:
                    item["date"] = date_str
                    # Inject date into the inner object for use in normalization
                    if "object" in item and isinstance(item["object"], dict):
                        item["ultrahuman_date"] = date_str
                return metrics
        except Exception as e:
            self.logger.warning(f"Failed to fetch metrics for {date_str}: {e}")
            # Don't swallow unexpected errors completely, but for daily sync we might want to continue
            # If it's a critical auth error it might be better to raise, but the base class usually handles auth.

        return []

    # -------------------------------------------------------------------------
    # Sleep Data
    # -------------------------------------------------------------------------

    def normalize_sleep(
        self,
        raw_sleep: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize Ultrahuman sleep data (from 'Sleep' type object) to our schema."""
        # Times are unix timestamps
        bedtime_start_ts = raw_sleep.get("bedtime_start")
        bedtime_end_ts = raw_sleep.get("bedtime_end")
        date_str = raw_sleep.get("ultrahuman_date")

        start_dt = None
        end_dt = None
        if bedtime_start_ts:
            start_dt = datetime.fromtimestamp(bedtime_start_ts, tz=timezone.utc)
        if bedtime_end_ts:
            end_dt = datetime.fromtimestamp(bedtime_end_ts, tz=timezone.utc)

        # Extract durations from quick_metrics
        # "quick_metrics": [{"type": "time_in_bed", "value": 27000}, ...]
        quick_metrics = {m.get("type"): m.get("value", 0) for m in raw_sleep.get("quick_metrics", [])}

        # Values are typically in seconds
        time_in_bed_seconds = quick_metrics.get("time_in_bed", 0) or 0

        # Extract sleep stages from sleep_stages array
        # "sleep_stages": [{"type": "deep_sleep", "stage_time": 3240}, ...]
        sleep_stages = {s.get("type"): s.get("stage_time", 0) for s in raw_sleep.get("sleep_stages", [])}
        deep_seconds = sleep_stages.get("deep_sleep", 0) or 0
        rem_seconds = sleep_stages.get("rem_sleep", 0) or 0
        light_seconds = sleep_stages.get("light_sleep", 0) or 0
        awake_seconds = sleep_stages.get("awake", 0) or 0

        # Efficiency from quick_metrics (type: "sleep_efic")
        efficiency = quick_metrics.get("sleep_efic")
        if efficiency is None:
            efficiency = raw_sleep.get("sleep_efficiency")

        internal_id = uuid4()

        return {
            "id": internal_id,
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": start_dt.isoformat() if start_dt else date_str,
            "start_time": start_dt,
            "end_time": end_dt,
            "duration_seconds": time_in_bed_seconds,
            "efficiency_percent": float(efficiency) if efficiency is not None else None,
            "is_nap": False,  # Ultrahuman doesn't explicitly mark naps in this structure
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
        start_dt = normalized_sleep.get("start_time")
        end_dt = normalized_sleep.get("end_time")

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
            external_id=f"sleep-{normalized_sleep.get('ultrahuman_date')}",
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

        # If total sleep is 0 but we have duration, try to infer
        if total_sleep_minutes == 0 and time_in_bed_minutes > 0:
            total_sleep_minutes = time_in_bed_minutes - (stages.get("awake_seconds", 0) // 60)

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

    def normalize_recovery(
        self,
        raw_recovery: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize Ultrahuman recovery data to our schema."""
        date_str = raw_recovery.get("ultrahuman_date")

        recovery_index = None
        movement_index = None
        metabolic_score = None

        if "recovery_index" in raw_recovery:
            recovery_index = raw_recovery["recovery_index"].get("value")

        if "movement_index" in raw_recovery:
            movement_index = raw_recovery["movement_index"].get("value")

        if "metabolic_score" in raw_recovery:
            metabolic_score = raw_recovery["metabolic_score"].get("value")

        return {
            "id": uuid4(),
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": date_str,
            "date": date_str,
            "recovery_index": recovery_index,
            "movement_index": movement_index,
            "metabolic_score": metabolic_score,
            "raw": raw_recovery,
        }

    # -------------------------------------------------------------------------
    # Activity Samples (HR, HRV, Temperature, Steps)
    # -------------------------------------------------------------------------

    def normalize_activity_samples(
        self,
        raw_samples: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, list[dict[str, Any]]]:
        """Normalize activity samples into categorized data.

        raw_samples keys: 'hr', 'hrv', 'temp', 'steps'
        """
        result = {
            "heart_rate": [],
            "hrv": [],
            "temperature": [],
            "steps": [],
        }

        # Heart rate samples
        if "hr" in raw_samples:
            values = raw_samples["hr"].get("values", [])
            for val in values:
                ts = val.get("timestamp")
                recorded_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None
                if recorded_at:
                    result["heart_rate"].append(
                        {
                            "id": uuid4(),
                            "user_id": user_id,
                            "provider": self.provider_name,
                            "recorded_at": recorded_at,
                            "value": val.get("value"),
                            "unit": "bpm",
                        }
                    )

        # HRV samples
        if "hrv" in raw_samples:
            values = raw_samples["hrv"].get("values", [])
            for val in values:
                ts = val.get("timestamp")
                recorded_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None
                if recorded_at:
                    result["hrv"].append(
                        {
                            "id": uuid4(),
                            "user_id": user_id,
                            "provider": self.provider_name,
                            "recorded_at": recorded_at,
                            "value": val.get("value"),
                            "unit": "ms",
                        }
                    )

        # Temperature samples (type='temp')
        if "temp" in raw_samples:
            values = raw_samples["temp"].get("values", [])
            for val in values:
                ts = val.get("timestamp")
                recorded_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None
                if recorded_at:
                    result["temperature"].append(
                        {
                            "id": uuid4(),
                            "user_id": user_id,
                            "provider": self.provider_name,
                            "recorded_at": recorded_at,
                            "value": val.get("value"),
                            "unit": "celsius",
                        }
                    )

        # Steps (type='steps')
        if "steps" in raw_samples:
            values = raw_samples["steps"].get("values", [])
            for val in values:
                ts = val.get("timestamp")
                steps_val = val.get("value")
                recorded_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None
                if recorded_at and steps_val and steps_val > 0:
                    result["steps"].append(
                        {
                            "id": uuid4(),
                            "user_id": user_id,
                            "provider": self.provider_name,
                            "recorded_at": recorded_at,
                            "value": steps_val,
                            "unit": "count",
                        }
                    )

        return result

    def save_activity_samples(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_samples: dict[str, list[dict[str, Any]]],
    ) -> int:
        """Save normalized activity samples (HR, HRV, etc.) to DataPointSeries."""
        count = 0

        # Map internal keys to SeriesType
        type_mapping = {
            "heart_rate": SeriesType.heart_rate,
            "hrv": SeriesType.heart_rate_variability_sdnn,
            "temperature": SeriesType.body_temperature,
            "steps": SeriesType.steps,
        }

        for key, samples in normalized_samples.items():
            series_type = type_mapping.get(key)
            if not series_type:
                continue

            for sample in samples:
                recorded_at_str = sample.get("recorded_at")
                try:
                    # Parse timestamp
                    if not recorded_at_str:
                        continue

                    recorded_at = datetime.fromisoformat(recorded_at_str.replace("Z", "+00:00"))

                    # Create sample
                    ts_sample = TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        provider_name=self.provider_name,
                        recorded_at=recorded_at,
                        value=Decimal(str(sample.get("value"))),
                        series_type=series_type,
                        external_device_mapping_id=None,
                    )

                    self.data_point_repo.create(db, ts_sample)
                    count += 1
                except Exception as e:
                    # Log but continue for other samples
                    # Use warning level for first few errors to help debug issues
                    self.logger.warning(
                        f"Failed to save {key} sample for user {user_id} at {recorded_at_str or 'unknown time'}: {e}"
                    )

        return count

    # -------------------------------------------------------------------------
    # Combined Load (Main Entry Point)
    # -------------------------------------------------------------------------

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
    ) -> dict[str, int]:
        """Load and save all 247 data types by fetching daily metrics."""

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
            "recovery_days_synced": 0,  # Placeholder, though we don't save recovery separately currently
        }

        current_date = start_time
        while current_date <= end_time:
            metrics_list = self._fetch_daily_metrics(db, user_id, current_date)
            date_str = current_date.strftime("%Y-%m-%d")

            # Group items by type
            items_by_type = {}
            for item in metrics_list:
                t = item.get("type")
                if t and "object" in item:
                    items_by_type[t] = item["object"]

            # 1. Process Sleep
            if "Sleep" in items_by_type:
                try:
                    normalized_sleep = self.normalize_sleep(items_by_type["Sleep"], user_id)
                    self.save_sleep_data(db, user_id, normalized_sleep)
                    results["sleep_sessions_synced"] += 1
                except Exception as e:
                    self.logger.error(f"Failed to process sleep for {date_str}: {e}")

            # 2. Process Recovery (Not saved to DB yet in this template, but logic is here)
            # We don't have a generic "save_recovery" in Base247DataTemplate or a table for it yet?
            # Actually EventRecord doesn't support generic daily recovery metrics easily without a specific type.
            # But we can normalize it if we add support later.

            # 3. Process Activity Samples
            try:
                # Prepare dict for normalization
                sample_inputs = {}
                for t in ["hr", "hrv", "temp", "steps"]:
                    if t in items_by_type:
                        sample_inputs[t] = items_by_type[t]

                normalized_samples = self.normalize_activity_samples(sample_inputs, user_id)
                saved_count = self.save_activity_samples(db, user_id, normalized_samples)
                results["activity_samples"] += saved_count
            except Exception as e:
                self.logger.error(f"Failed to process samples for {date_str}: {e}")

            current_date += timedelta(days=1)

        return results

    # Stub implementations for abstract methods that we don't use directly anymore
    # but might be required by the interface if strictly enforced (though python is loose)

    def get_sleep_data(self, *args, **kwargs) -> list[dict[str, Any]]:
        return []

    def get_recovery_data(self, *args, **kwargs) -> list[dict[str, Any]]:
        return []

    def get_activity_samples(self, *args, **kwargs) -> list[dict[str, Any]]:
        return []

    def get_daily_activity_statistics(self, *args, **kwargs) -> list[dict[str, Any]]:
        return []

    def normalize_daily_activity(self, *args, **kwargs) -> dict[str, Any]:
        return {}
