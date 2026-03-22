"""Sensr 247 data implementation for sleep, recovery, and biometrics."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.database import DbSession
from app.models import EventRecord
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.schemas import EventRecordCreate, TimeSeriesSampleCreate
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.schemas.series_types import SeriesType
from app.services.event_record_service import event_record_service
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.timeseries_service import timeseries_service
from app.utils.structured_logging import log_structured


class Sensr247Data(Base247DataTemplate):
    """Sensr implementation for 247 data (sleep, recovery, biometrics)."""

    def __init__(self, provider_name: str, api_base_url: str, oauth: BaseOAuthTemplate) -> None:
        super().__init__(provider_name, api_base_url, oauth)
        self.event_record_repo = EventRecordRepository(EventRecord)
        self.connection_repo = UserConnectionRepository()

    def _make_api_request(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
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

    @staticmethod
    def _from_epoch_seconds(timestamp: int | float | None) -> datetime | None:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp is not None else None

    @staticmethod
    def _from_epoch_millis(timestamp: int | float | None) -> datetime | None:
        return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc) if timestamp is not None else None

    def get_sleep_data(
        self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> list[dict[str, Any]]:
        all_sleep_data: list[dict[str, Any]] = []
        current_date = start_time.astimezone(timezone.utc).date()
        end_date = end_time.astimezone(timezone.utc).date()

        while current_date <= end_date:
            try:
                response = self._make_api_request(db, user_id, "/v1/sleep", params={"date": current_date.isoformat()})
                records = response.get("data", []) if isinstance(response, dict) else []
                if isinstance(records, list):
                    all_sleep_data.extend(records)
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Error fetching Sensr sleep for {current_date}: {e}",
                    provider="sensr",
                    task="get_sleep_data",
                )
            current_date += timedelta(days=1)

        return all_sleep_data

    def normalize_sleep(self, raw_sleep: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        biometrics = raw_sleep.get("biometrics", {}) or {}
        score = raw_sleep.get("score", {}) or {}
        start_dt = self._from_epoch_seconds(raw_sleep.get("start_timestamp"))
        end_dt = self._from_epoch_seconds(raw_sleep.get("end_timestamp"))
        duration_seconds = int((raw_sleep.get("total_sleep_mins") or 0) * 60)

        return {
            "id": uuid4(),
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": start_dt or end_dt,
            "start_time": start_dt,
            "end_time": end_dt,
            "duration_seconds": duration_seconds,
            "efficiency_percent": score.get("value"),
            "is_nap": duration_seconds < 3 * 3600 if duration_seconds else False,
            "stages": {
                "deep_seconds": int((raw_sleep.get("deep_sleep_mins") or 0) * 60),
                "light_seconds": int((raw_sleep.get("light_sleep_mins") or 0) * 60),
                "rem_seconds": int((raw_sleep.get("rem_sleep_mins") or 0) * 60),
                "awake_seconds": int((raw_sleep.get("awake_time_mins") or 0) * 60),
            },
            "average_heart_rate": biometrics.get("bpm") or raw_sleep.get("avg_heart_rate"),
            "average_hrv": biometrics.get("hrv"),
            "average_spo2": biometrics.get("spo2"),
            "resting_heart_rate": biometrics.get("resting_bpm"),
            "resting_hrv": biometrics.get("resting_hrv"),
            "sensr_sleep_id": raw_sleep.get("id") or raw_sleep.get("start_timestamp"),
            "raw": raw_sleep,
        }

    def save_sleep_data(self, db: DbSession, user_id: UUID, normalized_sleep: dict[str, Any]) -> None:
        sleep_id = normalized_sleep["id"]
        start_dt = normalized_sleep.get("start_time")
        end_dt = normalized_sleep.get("end_time")
        if not start_dt or not end_dt:
            log_structured(
                self.logger,
                "warning",
                "Skipping sleep record: missing start/end time",
                provider="sensr",
                task="save_sleep_data",
                sleep_id=str(sleep_id),
            )
            return

        record = EventRecordCreate(
            id=sleep_id,
            category="sleep",
            type="sleep_session",
            source_name="Sensor Bio",
            device_model=None,
            duration_seconds=normalized_sleep.get("duration_seconds"),
            start_datetime=start_dt,
            end_datetime=end_dt,
            external_id=str(normalized_sleep.get("sensr_sleep_id")) if normalized_sleep.get("sensr_sleep_id") else None,
            source=self.provider_name,
            user_id=user_id,
        )

        stages = normalized_sleep.get("stages", {})
        total_sleep_seconds = (
            stages.get("deep_seconds", 0) + stages.get("light_seconds", 0) + stages.get("rem_seconds", 0)
        )
        detail = EventRecordDetailCreate(
            record_id=sleep_id,
            sleep_total_duration_minutes=total_sleep_seconds // 60,
            sleep_time_in_bed_minutes=(normalized_sleep.get("duration_seconds") or 0) // 60,
            sleep_efficiency_score=Decimal(str(normalized_sleep["efficiency_percent"]))
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
            log_structured(
                self.logger,
                "error",
                f"Error saving sleep record {sleep_id}: {e}",
                provider="sensr",
                task="save_sleep_data",
            )

    def load_and_save_sleep(self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime) -> int:
        raw_data = self.get_sleep_data(db, user_id, start_time, end_time)
        count = 0
        for item in raw_data:
            try:
                normalized = self.normalize_sleep(item, user_id)
                self.save_sleep_data(db, user_id, normalized)
                count += 1
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to save sleep data: {e}",
                    provider="sensr",
                    task="load_and_save_sleep",
                )
        return count

    def get_recovery_data(
        self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> list[dict[str, Any]]:
        all_scores: list[dict[str, Any]] = []
        current_date = start_time.astimezone(timezone.utc).date()
        end_date = end_time.astimezone(timezone.utc).date()

        while current_date <= end_date:
            try:
                response = self._make_api_request(db, user_id, "/v1/scores", params={"date": current_date.isoformat()})
                record = response.get("data") if isinstance(response, dict) else None
                if isinstance(record, dict):
                    record["date"] = record.get("date") or current_date.isoformat()
                    all_scores.append(record)
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Error fetching Sensr scores for {current_date}: {e}",
                    provider="sensr",
                    task="get_recovery_data",
                )
            current_date += timedelta(days=1)

        return all_scores

    def normalize_recovery(self, raw_recovery: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        recovery = raw_recovery.get("recovery", {}) or {}
        sleep = raw_recovery.get("sleep", {}) or {}
        biometrics = sleep.get("biometrics", {}) or recovery.get("biometrics", {}) or {}
        date_str = raw_recovery.get("date")
        timestamp = datetime.fromisoformat(f"{date_str}T00:00:00+00:00") if date_str else None
        score_obj = recovery.get("score") if isinstance(recovery.get("score"), dict) else recovery
        return {
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": timestamp,
            "recovery_score": score_obj.get("value") if isinstance(score_obj, dict) else None,
            "resting_heart_rate": biometrics.get("resting_bpm"),
            "hrv_rmssd_milli": biometrics.get("resting_hrv") or biometrics.get("hrv"),
            "spo2_percentage": biometrics.get("spo2"),
            "raw": raw_recovery,
        }

    def save_recovery_data(self, db: DbSession, user_id: UUID, normalized_recovery: dict[str, Any]) -> int:
        timestamp = normalized_recovery.get("timestamp")
        if not timestamp:
            return 0

        count = 0
        metrics = [
            ("recovery_score", SeriesType.recovery_score),
            ("resting_heart_rate", SeriesType.resting_heart_rate),
            ("hrv_rmssd_milli", SeriesType.heart_rate_variability_rmssd),
            ("spo2_percentage", SeriesType.oxygen_saturation),
        ]
        for field_name, series_type in metrics:
            value = normalized_recovery.get(field_name)
            if value is None:
                continue
            try:
                sample = TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=timestamp,
                    value=Decimal(str(value)),
                    series_type=series_type,
                )
                timeseries_service.crud.create(db, sample)
                count += 1
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to save recovery {field_name}: {e}",
                    provider="sensr",
                    task="save_recovery_data",
                )
        return count

    def load_and_save_recovery(self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime) -> int:
        raw_data = self.get_recovery_data(db, user_id, start_time, end_time)
        total_count = 0
        for item in raw_data:
            try:
                normalized = self.normalize_recovery(item, user_id)
                total_count += self.save_recovery_data(db, user_id, normalized)
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to save recovery data: {e}",
                    provider="sensr",
                    task="load_and_save_recovery",
                )
        return total_count

    def get_activity_samples(
        self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> list[dict[str, Any]]:
        all_samples: list[dict[str, Any]] = []
        last_timestamp = 0
        limit = 50

        while True:
            try:
                response = self._make_api_request(
                    db, user_id, "/v1/biometrics", params={"last-timestamp": last_timestamp, "limit": limit}
                )
                records = response.get("data", []) if isinstance(response, dict) else []
                if not isinstance(records, list) or not records:
                    break

                filtered_records = []
                for record in records:
                    record_dt = self._from_epoch_millis(record.get("timestamp"))
                    if record_dt and start_time <= record_dt <= end_time:
                        filtered_records.append(record)
                all_samples.extend(filtered_records)

                next_timestamp = records[-1].get("timestamp")
                if next_timestamp is None or next_timestamp == last_timestamp:
                    break
                last_timestamp = int(next_timestamp)

                if not (response.get("links") or {}).get("next"):
                    break
            except Exception as e:
                log_structured(
                    self.logger,
                    "error",
                    f"Error fetching Sensr biometrics: {e}",
                    provider="sensr",
                    task="get_activity_samples",
                )
                if all_samples:
                    break
                raise

        return all_samples

    def normalize_activity_samples(
        self, raw_samples: list[dict[str, Any]], user_id: UUID
    ) -> dict[str, list[dict[str, Any]]]:
        normalized: dict[str, list[dict[str, Any]]] = {
            "heart_rate": [],
            "heart_rate_variability": [],
            "spo2": [],
            "respiratory_rate": [],
        }
        for sample in raw_samples:
            timestamp = self._from_epoch_millis(sample.get("timestamp"))
            if not timestamp:
                continue
            field_map = {
                "bpm": "heart_rate",
                "hrv": "heart_rate_variability",
                "spo2": "spo2",
                "brpm": "respiratory_rate",
            }
            for source_field, target_key in field_map.items():
                value = sample.get(source_field)
                if value is not None:
                    normalized[target_key].append({"user_id": user_id, "timestamp": timestamp, "value": value})
        return normalized

    def get_daily_activity_statistics(
        self, db: DbSession, user_id: UUID, start_date: datetime, end_date: datetime
    ) -> list[dict[str, Any]]:
        all_stats: list[dict[str, Any]] = []
        current_date = start_date.astimezone(timezone.utc).date()
        final_date = end_date.astimezone(timezone.utc).date()
        while current_date <= final_date:
            try:
                response = self._make_api_request(
                    db, user_id, "/v1/step/details", params={"date": current_date.isoformat(), "granularity": "day"}
                )
                data = response.get("data", response) if isinstance(response, dict) else None
                if isinstance(data, list):
                    all_stats.extend(data)
                elif isinstance(data, dict):
                    all_stats.append(data)
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Error fetching Sensr step details for {current_date}: {e}",
                    provider="sensr",
                    task="get_daily_activity_statistics",
                )
            current_date += timedelta(days=1)
        return all_stats

    def normalize_daily_activity(self, raw_stats: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": self._from_epoch_millis(raw_stats.get("timestamp")),
            "steps": raw_stats.get("steps"),
            "distance": raw_stats.get("distance"),
            "energy": raw_stats.get("total_step_calories"),
            "raw": raw_stats,
        }

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        is_first_sync: bool = False,
    ) -> dict[str, int]:
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        if not start_time:
            start_time = datetime.now(timezone.utc) - timedelta(days=30)
        if not end_time:
            end_time = datetime.now(timezone.utc)

        results = {
            "sleep_sessions_synced": 0,
            "recovery_samples_synced": 0,
            "activity_samples_synced": 0,
            "body_measurement_samples_synced": 0,
        }
        try:
            results["sleep_sessions_synced"] = self.load_and_save_sleep(db, user_id, start_time, end_time)
        except Exception as e:
            log_structured(
                self.logger, "error", f"Failed to sync sleep data: {e}", provider="sensr", task="load_and_save_all"
            )
        try:
            results["recovery_samples_synced"] = self.load_and_save_recovery(db, user_id, start_time, end_time)
        except Exception as e:
            log_structured(
                self.logger, "error", f"Failed to sync recovery data: {e}", provider="sensr", task="load_and_save_all"
            )
        return results
