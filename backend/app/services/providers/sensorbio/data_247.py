"""Sensor Bio 247 data implementation for sleep, recovery, biometrics, and daily activity."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ValidationError

from app.database import DbSession
from app.models import EventRecord
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.schemas.enums import HealthScoreCategory, ProviderName
from app.schemas.model_crud.activities import HealthScoreCreate
from app.schemas.model_crud.activities.data_point_series import TimeSeriesSampleCreate
from app.schemas.model_crud.activities.event_record import EventRecordCreate
from app.schemas.model_crud.activities.event_record_detail import EventRecordDetailCreate
from app.schemas.providers.sensorbio import (
    BiometricsRecord,
    ScoresRecord,
    SleepRecord,
    StepDetailsResponse,
)
from app.services.event_record_service import event_record_service
from app.services.health_score_service import health_score_service
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.sensorbio.coverage import (
    ACTIVITY_SAMPLE_SERIES,
    DAILY_ACTIVITY_SERIES,
    RECOVERY_SERIES,
)
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.raw_payload_storage import store_raw_payload
from app.services.timeseries_service import timeseries_service
from app.utils.structured_logging import log_structured

_SchemaT = TypeVar("_SchemaT", bound=BaseModel)


class SensorBio247Data(Base247DataTemplate):
    """Sensor Bio implementation for 247 data (sleep, recovery, biometrics, daily activity)."""

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
        """Make an authenticated request using HTTP/2 and store the raw payload.

        Sensor Bio requires HTTP/2 (see API docs). We pass ``http2=True`` to the
        underlying httpx client via ``make_authenticated_request``. This is a
        scoped override so other providers that use the shared api_client are
        unaffected.
        """
        result = make_authenticated_request(
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
            http2=True,
        )
        store_raw_payload(
            source="api_response",
            provider="sensorbio",
            payload=result,
            user_id=str(user_id),
            trace_id=endpoint,
        )
        return result

    def _parse(self, raw: dict[str, Any], schema: type[_SchemaT], context: str, user_id: UUID) -> _SchemaT | None:
        """Validate a raw API dict through a Pydantic schema.

        On ValidationError, log + return None (mirrors polar/data_247.py ~138-145).
        Callers skip None results rather than propagating bad data to DB writes.
        """
        try:
            return schema.model_validate(raw)
        except ValidationError as e:
            log_structured(
                self.logger,
                "warning",
                f"SensorBio {context} validation error — skipping record: {e}",
                provider="sensorbio",
                user_id=str(user_id),
                context=context,
            )
            return None

    @staticmethod
    def _from_epoch_seconds(timestamp: int | float | None) -> datetime | None:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp is not None else None

    @staticmethod
    def _from_epoch_millis(timestamp: int | float | None) -> datetime | None:
        return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc) if timestamp is not None else None

    # -------------------------------------------------------------------------
    # Sleep — GET /v1/sleep
    # -------------------------------------------------------------------------

    def get_sleep_data(
        self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> list[dict[str, Any]]:
        """Fetch sleep sessions for each local calendar day in the window.

        Sensor Bio's ``GET /v1/sleep`` accepts a single required ``date``
        parameter (YYYY-MM-DD). There is no multi-day range query for
        session-level sleep, so we must issue one request per day. A day may
        return multiple sessions (e.g. overnight sleep + nap).
        """
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
                    f"Error fetching Sensor Bio sleep for {current_date}: {e}",
                    provider="sensorbio",
                    task="get_sleep_data",
                )
            current_date += timedelta(days=1)

        return all_sleep_data

    def normalize_sleep(self, raw_sleep: dict[str, Any], user_id: UUID) -> dict[str, Any] | None:  # ty:ignore[invalid-method-override]
        """Validate + normalise a single /v1/sleep record.

        Returns None if the record fails Pydantic validation so the caller can skip it.

        NOTE: The official API intro states timestamps are milliseconds, but the
        sleep endpoint examples use epoch *seconds* for start/end. We keep
        ``_from_epoch_seconds`` to match observed response values.

        Sensor Bio does not expose an explicit nap flag. Multiple sessions on the
        same day are returned as separate entries; we leave ``is_nap=False``
        rather than inventing a duration heuristic.
        """
        parsed = self._parse(raw_sleep, SleepRecord, "sleep", user_id)
        if parsed is None:
            return None

        biometrics = parsed.biometrics
        score = parsed.score
        start_dt = self._from_epoch_seconds(parsed.start_timestamp)
        end_dt = self._from_epoch_seconds(parsed.end_timestamp)
        duration_seconds = int((parsed.total_sleep_mins or 0) * 60)

        return {
            "id": uuid4(),
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": start_dt or end_dt,
            "start_time": start_dt,
            "end_time": end_dt,
            "duration_seconds": duration_seconds,
            "efficiency_percent": score.value if score else None,
            "is_nap": False,
            "stages": {
                "deep_seconds": int((parsed.deep_sleep_mins or 0) * 60),
                "light_seconds": int((parsed.light_sleep_mins or 0) * 60),
                "rem_seconds": int((parsed.rem_sleep_mins or 0) * 60),
                "awake_seconds": int((parsed.awake_time_mins or 0) * 60),
            },
            "average_heart_rate": (biometrics.bpm if biometrics else None) or parsed.avg_heart_rate,
            "average_hrv": biometrics.hrv if biometrics else None,
            "average_spo2": biometrics.spo2 if biometrics else None,
            "resting_heart_rate": biometrics.resting_bpm if biometrics else None,
            "resting_hrv": biometrics.resting_hrv if biometrics else None,
            "sensorbio_sleep_id": raw_sleep.get("id") or raw_sleep.get("start_timestamp"),
            "raw": raw_sleep,
        }

    def save_sleep_data(self, db: DbSession, user_id: UUID, normalized_sleep: dict[str, Any]) -> bool:
        """Persist a normalized sleep record. Returns True on success, False when skipped or on error."""
        sleep_id = normalized_sleep["id"]
        start_dt = normalized_sleep.get("start_time")
        end_dt = normalized_sleep.get("end_time")
        if not start_dt or not end_dt:
            log_structured(
                self.logger,
                "warning",
                "Skipping sleep record: missing start/end time",
                provider="sensorbio",
                task="save_sleep_data",
                sleep_id=str(sleep_id),
            )
            return False

        record = EventRecordCreate(
            id=sleep_id,
            category="sleep",
            type="sleep_session",
            source_name="Sensor Bio",
            device_model=None,
            duration_seconds=normalized_sleep.get("duration_seconds"),
            start_datetime=start_dt,
            end_datetime=end_dt,
            external_id=str(normalized_sleep.get("sensorbio_sleep_id"))
            if normalized_sleep.get("sensorbio_sleep_id")
            else None,
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
            return True
        except Exception as e:
            log_structured(
                self.logger,
                "error",
                f"Error saving sleep record {sleep_id}: {e}",
                provider="sensorbio",
                task="save_sleep_data",
            )
            return False

    def load_and_save_sleep(self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime) -> int:
        raw_data = self.get_sleep_data(db, user_id, start_time, end_time)
        count = 0
        for item in raw_data:
            try:
                normalized = self.normalize_sleep(item, user_id)
                if normalized is None:
                    continue
                if self.save_sleep_data(db, user_id, normalized):
                    count += 1
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to save sleep data: {e}",
                    provider="sensorbio",
                    task="load_and_save_sleep",
                )
        return count

    # -------------------------------------------------------------------------
    # Recovery — GET /v1/scores
    # -------------------------------------------------------------------------

    def get_recovery_data(
        self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> list[dict[str, Any]]:
        """Fetch daily scores for each local calendar day in the window.

        Sensor Bio's ``GET /v1/scores`` accepts a single required ``date``
        parameter. There is no multi-day range for the top-level scores payload
        (activity + sleep + recovery), so we issue one request per day.
        """
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
                    f"Error fetching Sensor Bio scores for {current_date}: {e}",
                    provider="sensorbio",
                    task="get_recovery_data",
                )
            current_date += timedelta(days=1)

        return all_scores

    def normalize_recovery(self, raw_recovery: dict[str, Any], user_id: UUID) -> dict[str, Any] | None:  # ty:ignore[invalid-method-override]
        """Validate + normalise a /v1/scores record (recovery + activity + sleep scores).

        Returns None on validation failure so the caller can skip cleanly.
        """
        parsed = self._parse(raw_recovery, ScoresRecord, "scores", user_id)
        if parsed is None:
            return None

        recovery = parsed.recovery
        sleep = parsed.sleep
        biometrics = sleep.biometrics if sleep else None
        date_str = parsed.date
        timestamp = datetime.fromisoformat(f"{date_str}T00:00:00+00:00") if date_str else None

        recovery_score = recovery.value if recovery else None
        activity = parsed.activity
        activity_score = activity.value if activity else None
        sleep_score = sleep.value if sleep else None

        return {
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": timestamp,
            "recovery_score": recovery_score,
            "recovery_stage": recovery.stage if recovery else None,
            "activity_score": activity_score,
            "sleep_score": sleep_score,
            "resting_heart_rate": biometrics.resting_bpm if biometrics else None,
            "hrv_rmssd_milli": (biometrics.resting_hrv if biometrics else None)
            or (biometrics.hrv if biometrics else None),
            "spo2_percentage": biometrics.spo2 if biometrics else None,
            "raw": raw_recovery,
        }

    def save_recovery_data(self, db: DbSession, user_id: UUID, normalized_recovery: dict[str, Any]) -> dict[str, int]:
        """Persist normalized recovery data: biometric timeseries + health scores.

        Returns ``{\"metrics_synced\": N, \"scores_synced\": M}`` so callers can
        log and surface the two categories separately.
        """
        timestamp = normalized_recovery.get("timestamp")
        if not timestamp:
            return {"metrics_synced": 0, "scores_synced": 0}

        samples: list[TimeSeriesSampleCreate] = []
        for field_name, series_type in RECOVERY_SERIES.items():
            value = normalized_recovery.get(field_name)
            if value is None:
                continue
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=timestamp,
                    value=Decimal(str(value)),
                    series_type=series_type,
                )
            )

        metrics_synced = 0
        if samples:
            try:
                metrics_synced = int(timeseries_service.bulk_create_samples(db, samples))
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to bulk-save recovery metrics: {e}",
                    provider="sensorbio",
                    task="save_recovery_data",
                )
                metrics_synced = 0

        health_scores: list[HealthScoreCreate] = []
        recovery_score = normalized_recovery.get("recovery_score")
        if recovery_score is not None:
            health_scores.append(
                HealthScoreCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider=ProviderName.SENSORBIO,
                    category=HealthScoreCategory.RECOVERY,
                    value=recovery_score,
                    qualifier=normalized_recovery.get("recovery_stage"),
                    recorded_at=timestamp,
                )
            )
        activity_score = normalized_recovery.get("activity_score")
        if activity_score is not None:
            health_scores.append(
                HealthScoreCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider=ProviderName.SENSORBIO,
                    category=HealthScoreCategory.ACTIVITY,
                    value=activity_score,
                    recorded_at=timestamp,
                )
            )
        sleep_score = normalized_recovery.get("sleep_score")
        if sleep_score is not None:
            health_scores.append(
                HealthScoreCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider=ProviderName.SENSORBIO,
                    category=HealthScoreCategory.SLEEP,
                    value=sleep_score,
                    recorded_at=timestamp,
                )
            )

        scores_synced = 0
        if health_scores:
            try:
                health_score_service.bulk_create(db, health_scores)
                scores_synced = len(health_scores)
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to bulk-save recovery health scores: {e}",
                    provider="sensorbio",
                    task="save_recovery_data",
                )
                scores_synced = 0

        return {"metrics_synced": metrics_synced, "scores_synced": scores_synced}

    def load_and_save_recovery(
        self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> dict[str, int]:
        raw_data = self.get_recovery_data(db, user_id, start_time, end_time)
        totals = {"metrics_synced": 0, "scores_synced": 0}
        for item in raw_data:
            try:
                normalized = self.normalize_recovery(item, user_id)
                if normalized is None:
                    continue
                counts = self.save_recovery_data(db, user_id, normalized)
                totals["metrics_synced"] += counts["metrics_synced"]
                totals["scores_synced"] += counts["scores_synced"]
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to save recovery data: {e}",
                    provider="sensorbio",
                    task="load_and_save_recovery",
                )
        log_structured(
            self.logger,
            "info",
            "Sensor Bio recovery sync complete",
            provider="sensorbio",
            task="load_and_save_recovery",
            user_id=str(user_id),
            metrics_synced=totals["metrics_synced"],
            scores_synced=totals["scores_synced"],
        )
        return totals

    # -------------------------------------------------------------------------
    # Biometric activity samples — GET /v1/biometrics (cursor-paginated)
    # -------------------------------------------------------------------------

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
                    f"Error fetching Sensor Bio biometrics: {e}",
                    provider="sensorbio",
                    task="get_activity_samples",
                )
                if all_samples:
                    break
                raise

        return all_samples

    def normalize_activity_samples(
        self, raw_samples: list[dict[str, Any]], user_id: UUID
    ) -> dict[str, list[dict[str, Any]]]:
        normalized: dict[str, list[dict[str, Any]]] = {key: [] for key in ACTIVITY_SAMPLE_SERIES}
        field_map = {
            "bpm": "heart_rate",
            "hrv": "heart_rate_variability",
            "spo2": "spo2",
            "brpm": "respiratory_rate",
        }
        for raw in raw_samples:
            parsed = self._parse(raw, BiometricsRecord, "biometrics", user_id)
            if parsed is None:
                continue
            timestamp = self._from_epoch_millis(parsed.timestamp)
            if not timestamp:
                continue
            for source_field, target_key in field_map.items():
                value = getattr(parsed, source_field, None)
                if value is not None:
                    normalized[target_key].append({"user_id": user_id, "timestamp": timestamp, "value": value})
        return normalized

    def save_activity_samples(
        self, db: DbSession, user_id: UUID, normalized_samples: dict[str, list[dict[str, Any]]]
    ) -> int:
        """Persist normalized biometric activity samples as timeseries entries."""
        all_samples: list[TimeSeriesSampleCreate] = []
        for key, samples in normalized_samples.items():
            series_type = ACTIVITY_SAMPLE_SERIES.get(key)
            if not series_type:
                continue
            for sample in samples:
                timestamp = sample.get("timestamp")
                value = sample.get("value")
                if timestamp is None or value is None:
                    continue
                all_samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=timestamp,
                        value=Decimal(str(value)),
                        series_type=series_type,
                    )
                )
        if all_samples:
            try:
                timeseries_service.bulk_create_samples(db, all_samples)
            except Exception as e:
                log_structured(
                    self.logger,
                    "error",
                    f"Failed to bulk-save {len(all_samples)} activity samples: {e}",
                    provider="sensorbio",
                    task="save_activity_samples",
                )
                return 0
        return len(all_samples)

    # -------------------------------------------------------------------------
    # Daily activity (steps/energy/distance) — GET /v1/step/details
    # -------------------------------------------------------------------------

    def get_daily_activity_statistics(
        self, db: DbSession, user_id: UUID, start_date: datetime, end_date: datetime
    ) -> list[dict[str, Any]]:
        """Fetch step details per day from /v1/step/details.

        Like sleep/scores, this endpoint is date-scoped (``date`` + ``granularity``).
        """
        all_stats: list[dict[str, Any]] = []
        current_date = start_date.astimezone(timezone.utc).date()
        final_date = end_date.astimezone(timezone.utc).date()
        while current_date <= final_date:
            try:
                response = self._make_api_request(
                    db, user_id, "/v1/step/details", params={"date": current_date.isoformat(), "granularity": "day"}
                )
                if isinstance(response, dict) and "metrics" in response:
                    all_stats.append(response)
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Error fetching Sensor Bio step details for {current_date}: {e}",
                    provider="sensorbio",
                    task="get_daily_activity_statistics",
                )
            current_date += timedelta(days=1)
        return all_stats

    def normalize_daily_activity(self, raw_stats: dict[str, Any], user_id: UUID) -> dict[str, Any] | None:  # ty:ignore[invalid-method-override]
        """Validate + normalise a StepDetailsResponseBody into our internal shape."""
        parsed = self._parse(raw_stats, StepDetailsResponse, "step_details", user_id)
        if parsed is None:
            return None

        metrics_by_name: dict[str, Any] = {}
        for metric in parsed.metrics:
            name = metric.name or metric.type
            if name:
                metrics_by_name[name] = metric

        date_str = parsed.date
        timestamp = datetime.fromisoformat(f"{date_str}T00:00:00+00:00") if date_str else None

        steps_metric = metrics_by_name.get("Steps")
        distance_metric = metrics_by_name.get("Distance")
        calories_metric = metrics_by_name.get("Calories")

        return {
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": timestamp,
            "steps": int(steps_metric.value) if steps_metric and steps_metric.value is not None else None,
            "distance": distance_metric.value if distance_metric else None,
            "energy": calories_metric.value if calories_metric else None,
            "raw": raw_stats,
        }

    def save_daily_activity(self, db: DbSession, user_id: UUID, normalized_activity: dict[str, Any]) -> int:
        """Persist steps/energy/distance_walking_running as daily-total timeseries."""
        timestamp = normalized_activity.get("timestamp")
        if not timestamp:
            return 0

        samples: list[TimeSeriesSampleCreate] = []
        for field_name, series_type in DAILY_ACTIVITY_SERIES.items():
            value = normalized_activity.get(field_name)
            if value is None:
                continue
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=timestamp,
                    value=Decimal(str(value)),
                    series_type=series_type,
                    is_daily_total=True,
                )
            )

        if samples:
            try:
                timeseries_service.bulk_create_samples(db, samples)
            except Exception as e:
                log_structured(
                    self.logger,
                    "error",
                    f"Failed to bulk-save {len(samples)} daily activity samples: {e}",
                    provider="sensorbio",
                    task="save_daily_activity",
                )
                return 0

        return len(samples)

    def load_and_save_daily_activity(
        self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> int:
        """Fetch, normalize, and persist daily step/distance/energy data."""
        raw_data = self.get_daily_activity_statistics(db, user_id, start_time, end_time)
        total_count = 0
        for item in raw_data:
            try:
                normalized = self.normalize_daily_activity(item, user_id)
                if normalized is None:
                    continue
                total_count += self.save_daily_activity(db, user_id, normalized)
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to save daily activity data: {e}",
                    provider="sensorbio",
                    task="load_and_save_daily_activity",
                )
        return total_count

    # -------------------------------------------------------------------------
    # Orchestration — load_and_save_all with commit/rollback discipline
    # -------------------------------------------------------------------------

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

        results: dict[str, int] = {
            "sleep_sessions_synced": 0,
            "recovery_metrics_synced": 0,
            "recovery_scores_synced": 0,
            "activity_samples_synced": 0,
            "daily_activity_synced": 0,
        }

        try:
            results["sleep_sessions_synced"] = self.load_and_save_sleep(db, user_id, start_time, end_time)
            db.commit()
        except Exception as e:
            db.rollback()
            log_structured(
                self.logger, "error", f"Failed to sync sleep data: {e}", provider="sensorbio", task="load_and_save_all"
            )

        try:
            recovery_counts = self.load_and_save_recovery(db, user_id, start_time, end_time)
            results["recovery_metrics_synced"] = recovery_counts["metrics_synced"]
            results["recovery_scores_synced"] = recovery_counts["scores_synced"]
            db.commit()
        except Exception as e:
            db.rollback()
            log_structured(
                self.logger,
                "error",
                f"Failed to sync recovery data: {e}",
                provider="sensorbio",
                task="load_and_save_all",
            )

        try:
            raw_activity = self.get_activity_samples(db, user_id, start_time, end_time)
            normalized_activity = self.normalize_activity_samples(raw_activity, user_id)
            results["activity_samples_synced"] = self.save_activity_samples(db, user_id, normalized_activity)
            db.commit()
        except Exception as e:
            db.rollback()
            log_structured(
                self.logger,
                "error",
                f"Failed to sync activity samples: {e}",
                provider="sensorbio",
                task="load_and_save_all",
            )

        try:
            results["daily_activity_synced"] = self.load_and_save_daily_activity(db, user_id, start_time, end_time)
            db.commit()
        except Exception as e:
            db.rollback()
            log_structured(
                self.logger,
                "error",
                f"Failed to sync daily activity data: {e}",
                provider="sensorbio",
                task="load_and_save_all",
            )

        log_structured(
            self.logger,
            "info",
            "Sensor Bio 247 sync complete",
            provider="sensorbio",
            task="load_and_save_all",
            user_id=str(user_id),
            **results,
        )
        return results
