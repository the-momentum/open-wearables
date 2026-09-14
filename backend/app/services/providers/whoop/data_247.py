"""Whoop 247 Data implementation for sleep, recovery, and activity samples."""

from contextlib import suppress
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.config import settings
from app.database import DbSession
from app.models import DataPointSeries, DataSource, EventRecord
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas.enums import HealthScoreCategory, ProviderName, SeriesType, get_series_type_id
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    HealthScoreCreate,
    ScoreComponent,
    TimeSeriesSampleCreate,
)
from app.services.event_record_service import event_record_service
from app.services.health_score_service import health_score_service
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.whoop.coverage import RECOVERY_SERIES
from app.services.raw_payload_storage import store_raw_payload
from app.services.timeseries_service import timeseries_service
from app.utils.conversion import kilojoules_to_kcal
from app.utils.dates import to_rfc3339
from app.utils.structured_logging import log_structured

_MAX_PAGE_LIMIT = 25  # Whoop API limit

_SLEEP_ENDPOINT = "/v2/activity/sleep"
_RECOVERY_ENDPOINT = "/v2/recovery"
_CYCLE_ENDPOINT = "/v2/cycle"


class Whoop247Data(Base247DataTemplate):
    """Whoop implementation for 247 data (sleep, recovery, activity)."""

    def __init__(
        self,
        provider_name: str,
        api_base_url: str,
        oauth: BaseOAuthTemplate,
    ):
        super().__init__(provider_name, api_base_url, oauth)
        self.event_record_repo = EventRecordRepository(EventRecord)
        self.data_source_repo = DataSourceRepository(DataSource)
        self.connection_repo = UserConnectionRepository()

    def _make_api_request(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make authenticated request to Whoop API."""
        log_structured(
            self.logger,
            "debug",
            f"Making API request to {endpoint}",
            provider="whoop",
            endpoint=endpoint,
            params=params,
        )
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
    # Sleep Data - Whoop /v2/activity/sleep
    # -------------------------------------------------------------------------

    def _fetch_paginated(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        start_time: datetime,
        end_time: datetime,
        label: str,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Fetch every page of a paginated Whoop collection endpoint.

        Returns (records, truncated). truncated means a page failed and the range is
        incomplete — nothing re-fetches it, so callers keep the records they got and
        report the gap rather than discarding real data.

        label names the data for logging; task follows the get_{label}_data convention.
        """
        task = f"get_{label}_data"
        all_records: list[dict[str, Any]] = []
        next_token = None
        start_iso = to_rfc3339(start_time)
        end_iso = to_rfc3339(end_time)

        while True:
            params: dict[str, Any] = {
                "start": start_iso,
                "end": end_iso,
                "limit": _MAX_PAGE_LIMIT,
            }

            if next_token:
                params["nextToken"] = next_token

            try:
                response = self._make_api_request(db, user_id, endpoint, params=params)
                store_raw_payload(
                    source="api_response",
                    provider="whoop",
                    payload=response,
                    user_id=str(user_id),
                    trace_id=endpoint,
                )

                records = response.get("records", []) if isinstance(response, dict) else []
                all_records.extend(records)
                next_token = response.get("next_token") if isinstance(response, dict) else None

                if not records or not next_token:
                    break

            except Exception as e:
                log_structured(
                    self.logger,
                    "error",
                    f"Error fetching Whoop {label} data: {e}",
                    provider="whoop",
                    task=task,
                    user_id=str(user_id),
                )
                # Page 1 failing means we have nothing to save, so let it propagate.
                if not all_records:
                    raise
                log_structured(
                    self.logger,
                    "warning",
                    f"Returning partial {label} data due to error: {e}",
                    provider="whoop",
                    task=task,
                    action="whoop_api_partial_data",
                    user_id=str(user_id),
                )
                return all_records, True

        return all_records, False

    def get_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch sleep data from Whoop API via v2 endpoint with pagination.

        Drops the truncation flag to keep the Base247DataTemplate contract; callers
        that need it (load_and_save_sleep) use _fetch_paginated directly.
        """
        return self._fetch_paginated(db, user_id, _SLEEP_ENDPOINT, start_time, end_time, "sleep")[0]

    def _normalize_sleep_health_score(
        self,
        normalized: dict[str, Any],
        user_id: UUID,
    ) -> HealthScoreCreate | None:
        """Build a HealthScoreCreate for Whoop sleep score."""
        if normalized.get("score_state") != "SCORED":
            return None
        performance = normalized.get("sleep_performance_percentage")
        timestamp = normalized.get("timestamp")
        if performance is None or timestamp is None:
            return None
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return None
        components = {
            k: ScoreComponent(value=v)
            for k, v in {
                "sleep_consistency_percentage": normalized.get("sleep_consistency_percentage"),
                "sleep_efficiency_percentage": normalized.get("sleep_efficiency_percentage"),
                "respiratory_rate": normalized.get("respiratory_rate"),
            }.items()
            if v is not None
        }
        return HealthScoreCreate(
            id=uuid4(),
            user_id=user_id,
            provider=ProviderName.WHOOP,
            category=HealthScoreCategory.SLEEP,
            value=performance,
            recorded_at=timestamp,
            components=components or None,
        )

    def normalize_sleep(
        self,
        raw_sleep: dict[str, Any],
        user_id: UUID,
    ) -> tuple[dict[str, Any], HealthScoreCreate | None]:  # ty:ignore[invalid-method-override]
        """Normalize Whoop sleep data to our schema."""
        # Extract basic fields
        sleep_id = raw_sleep.get("id")
        start_time = raw_sleep.get("start")
        end_time = raw_sleep.get("end")
        nap = raw_sleep.get("nap", False)
        cycle_id = raw_sleep.get("cycle_id")
        zone_offset = raw_sleep.get("zone_offset")

        # Extract score data (may be None if not scored yet)
        score = raw_sleep.get("score", {}) or {}
        stage_summary = score.get("stage_summary", {}) or {}

        # Time conversions: Whoop provides durations in milliseconds
        # Convert to seconds for our schema
        total_in_bed_ms = stage_summary.get("total_in_bed_time_milli", 0)
        total_awake_ms = stage_summary.get("total_awake_time_milli", 0)
        total_light_ms = stage_summary.get("total_light_sleep_time_milli", 0)
        total_slow_wave_ms = stage_summary.get("total_slow_wave_sleep_time_milli", 0)
        total_rem_ms = stage_summary.get("total_rem_sleep_time_milli", 0)

        # Convert milliseconds to seconds
        duration_seconds = int(total_in_bed_ms / 1000) if total_in_bed_ms else 0
        deep_seconds = int(total_slow_wave_ms / 1000) if total_slow_wave_ms else 0
        light_seconds = int(total_light_ms / 1000) if total_light_ms else 0
        rem_seconds = int(total_rem_ms / 1000) if total_rem_ms else 0
        awake_seconds = int(total_awake_ms / 1000) if total_awake_ms else 0

        # If duration is 0 but we have start/end times, calculate from timestamps
        if duration_seconds == 0 and start_time and end_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                duration_seconds = int((end_dt - start_dt).total_seconds())
            except (ValueError, AttributeError):
                pass

        # Efficiency percentage
        efficiency = score.get("sleep_efficiency_percentage")

        # Generate UUID for our internal ID (use Whoop ID if it's a valid UUID string)
        internal_id = uuid4()
        if sleep_id:
            with suppress(ValueError, TypeError):
                internal_id = UUID(sleep_id)

        normalized = {
            "id": internal_id,
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": start_time or end_time,
            "start_time": start_time,
            "end_time": end_time,
            "zone_offset": zone_offset,
            "duration_seconds": duration_seconds,
            "efficiency_percent": float(efficiency) if efficiency is not None else None,
            "is_nap": nap,
            "stages": {
                "deep_seconds": deep_seconds,
                "light_seconds": light_seconds,
                "rem_seconds": rem_seconds,
                "awake_seconds": awake_seconds,
            },
            "whoop_sleep_id": sleep_id,
            "whoop_cycle_id": cycle_id,
            "score_state": raw_sleep.get("score_state"),
            "sleep_performance_percentage": score.get("sleep_performance_percentage"),
            "sleep_consistency_percentage": score.get("sleep_consistency_percentage"),
            "sleep_efficiency_percentage": efficiency,
            "respiratory_rate": score.get("respiratory_rate"),
            "raw": raw_sleep,  # Keep raw for debugging
        }
        return normalized, self._normalize_sleep_health_score(normalized, user_id)

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
            log_structured(
                self.logger,
                "warning",
                f"Skipping sleep record {sleep_id}: missing start/end time",
                provider="whoop",
                task="save_sleep_data",
                user_id=str(user_id),
            )
            return

        # Create EventRecord for sleep
        record = EventRecordCreate(
            id=sleep_id,
            category="sleep",
            type="sleep_session",
            source_name="Whoop",
            device_model=None,
            duration_seconds=normalized_sleep.get("duration_seconds"),
            start_datetime=start_dt,
            end_datetime=end_dt,
            zone_offset=normalized_sleep.get("zone_offset"),
            external_id=str(normalized_sleep.get("whoop_sleep_id")) if normalized_sleep.get("whoop_sleep_id") else None,
            source=self.provider_name,
            user_id=user_id,
        )

        # Create detail with sleep-specific fields
        stages = normalized_sleep.get("stages", {})
        # Calculate total sleep time (deep + light + REM)
        total_sleep_seconds = (
            stages.get("deep_seconds", 0) + stages.get("light_seconds", 0) + stages.get("rem_seconds", 0)
        )
        total_sleep_minutes = total_sleep_seconds // 60

        # Time in bed (total duration)
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
            event_record_service.create_or_merge_sleep(db, user_id, record, detail, settings.sleep_end_gap_minutes)
        except Exception as e:
            log_structured(
                self.logger,
                "error",
                f"Error saving sleep record {sleep_id}: {e}",
                provider="whoop",
                task="save_sleep_data",
                user_id=str(user_id),
            )

    def get_sleep_record(
        self,
        db: DbSession,
        user_id: UUID,
        sleep_id: str,
    ) -> dict[str, Any]:
        """Fetch a single sleep record by its Whoop ID from /v2/activity/sleep/{id}."""
        response = self._make_api_request(db, user_id, f"/v2/activity/sleep/{sleep_id}")
        store_raw_payload(
            source="api_response",
            provider="whoop",
            payload=response,
            user_id=str(user_id),
            trace_id=f"/v2/activity/sleep/{sleep_id}",
        )
        return response if isinstance(response, dict) else {}

    def load_single_sleep(
        self,
        db: DbSession,
        user_id: UUID,
        sleep_id: str,
    ) -> tuple[int, str | None]:
        """Fetch a single sleep record by ID, normalize, and save to database.

        Returns (saved, cycle_id). The cycle_id rides along so the caller can refresh the
        cycle this sleep just closed without fetching the same payload twice.
        """
        raw = self.get_sleep_record(db, user_id, sleep_id)
        if not raw:
            return 0, None
        cycle_id = raw.get("cycle_id")
        cycle_id = str(cycle_id) if cycle_id else None
        try:
            normalized, health_score = self.normalize_sleep(raw, user_id)
            self.save_sleep_data(db, user_id, normalized)
            if health_score:
                health_score_service.create(db, health_score)
            return 1, cycle_id
        except Exception as e:
            log_structured(
                self.logger,
                "warning",
                f"Failed to save sleep record {sleep_id}: {e}",
                provider="whoop",
                task="load_single_sleep",
            )
            return 0, cycle_id

    def load_and_save_sleep(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> tuple[int, bool]:
        """Load sleep data from API and save to database. Returns (saved, partial)."""
        raw_data, truncated = self._fetch_paginated(db, user_id, _SLEEP_ENDPOINT, start_time, end_time, "sleep")
        count = 0
        health_scores: list[HealthScoreCreate] = []
        for item in raw_data:
            try:
                normalized, health_score = self.normalize_sleep(item, user_id)
                self.save_sleep_data(db, user_id, normalized)
                count += 1
                if health_score:
                    health_scores.append(health_score)
            except Exception as e:
                db.rollback()
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to save sleep data: {e}",
                    provider="whoop",
                    task="load_and_save_sleep",
                    user_id=str(user_id),
                )
        if health_scores:
            health_score_service.bulk_create(db, health_scores)
            db.commit()
        return count, truncated

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        is_first_sync: bool = False,
    ) -> dict[str, int]:
        """Load and save all 247 data types (sleep, recovery, activity).

        Args:
            db: Database session
            user_id: User UUID
            start_time: Start of date range (defaults to 30 days ago)
            end_time: End of date range (defaults to now)
            is_first_sync: Whether this is the first sync (unused, for API compatibility)
        """
        # Handle date defaults (last 30 days if not specified)
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
            "cycles_synced": 0,
            "body_measurement_samples_synced": 0,
        }

        try:
            saved, sleep_partial = self.load_and_save_sleep(db, user_id, start_time, end_time)
            results["sleep_sessions_synced"] = saved
            if sleep_partial:
                results["sleep_partial"] = 1
        except Exception as e:
            db.rollback()
            log_structured(
                self.logger,
                "error",
                f"Failed to sync sleep data: {e}",
                provider="whoop",
                task="load_and_save_all",
                user_id=str(user_id),
            )

        try:
            saved, recovery_partial = self.load_and_save_recovery(db, user_id, start_time, end_time)
            results["recovery_samples_synced"] = saved
            if recovery_partial:
                results["recovery_partial"] = 1
        except Exception as e:
            db.rollback()
            log_structured(
                self.logger,
                "error",
                f"Failed to sync recovery data: {e}",
                provider="whoop",
                task="load_and_save_all",
                user_id=str(user_id),
            )

        try:
            saved, cycles_partial = self.load_and_save_cycles(db, user_id, start_time, end_time)
            results["cycles_synced"] = saved
            if cycles_partial:
                results["cycles_partial"] = 1
        except Exception as e:
            db.rollback()
            log_structured(
                self.logger,
                "error",
                f"Failed to sync cycle data: {e}",
                provider="whoop",
                task="load_and_save_all",
                user_id=str(user_id),
            )

        try:
            results["body_measurement_samples_synced"] = self.load_and_save_body_measurement(db, user_id)
        except Exception as e:
            db.rollback()
            log_structured(
                self.logger,
                "error",
                f"Failed to sync body measurement data: {e}",
                provider="whoop",
                task="load_and_save_all",
                user_id=str(user_id),
            )

        return results

    # -------------------------------------------------------------------------
    # Body Measurement Data (Height/Weight)
    # -------------------------------------------------------------------------

    def get_body_measurement(
        self,
        db: DbSession,
        user_id: UUID,
    ) -> dict[str, Any]:
        """Fetch body measurements from Whoop API.

        Returns height_meter, weight_kilogram, and max_heart_rate.
        See: https://developer.whoop.com/api/#tag/Body-Measurement
        """
        try:
            response = self._make_api_request(db, user_id, "/v2/user/measurement/body")
            store_raw_payload(
                source="api_response",
                provider="whoop",
                payload=response,
                user_id=str(user_id),
                trace_id="/v2/user/measurement/body",
            )
            return response if isinstance(response, dict) else {}
        except Exception as e:
            log_structured(
                self.logger,
                "error",
                f"Error fetching Whoop body measurement: {e}",
                provider="whoop",
                task="get_body_measurement",
                user_id=str(user_id),
            )
            return {}

    def _get_latest_value(
        self,
        db: DbSession,
        user_id: UUID,
        series_type: SeriesType,
    ) -> Decimal | None:
        """Get the most recent value for a series type for this user/provider."""
        type_id = get_series_type_id(series_type)
        result = (
            db.query(DataPointSeries.value)
            .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
            .filter(
                DataSource.user_id == user_id,
                DataSource.source == self.provider_name,
                DataPointSeries.series_type_definition_id == type_id,
            )
            .order_by(DataPointSeries.recorded_at.desc())
            .first()
        )
        return result[0] if result else None

    def load_and_save_body_measurement(
        self,
        db: DbSession,
        user_id: UUID,
    ) -> int:
        """Fetch body measurements and save height/weight to data_point_series.

        Only saves if the value has changed from the most recent entry.
        Returns the number of samples saved.
        """
        body = self.get_body_measurement(db, user_id)
        if not body:
            return 0

        recorded_at = datetime.now(timezone.utc)
        samples_to_create: list[TimeSeriesSampleCreate] = []

        # Save height (convert meters to centimeters) if changed
        height_meter = body.get("height_meter")
        if height_meter is not None:
            try:
                height_cm = Decimal(str(height_meter)) * 100
                latest_height = self._get_latest_value(db, user_id, SeriesType.height)

                if latest_height is None or abs(latest_height - height_cm) > Decimal("0.01"):
                    samples_to_create.append(
                        TimeSeriesSampleCreate(
                            id=uuid4(),
                            user_id=user_id,
                            source=self.provider_name,
                            recorded_at=recorded_at,
                            value=height_cm,
                            series_type=SeriesType.height,
                        )
                    )
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to build height sample: {e}",
                    provider="whoop",
                    task="load_and_save_body_measurement",
                    user_id=str(user_id),
                )

        # Save weight (already in kilograms) if changed
        weight_kg = body.get("weight_kilogram")
        if weight_kg is not None:
            try:
                weight = Decimal(str(weight_kg))
                latest_weight = self._get_latest_value(db, user_id, SeriesType.weight)

                if latest_weight is None or abs(latest_weight - weight) > Decimal("0.01"):
                    samples_to_create.append(
                        TimeSeriesSampleCreate(
                            id=uuid4(),
                            user_id=user_id,
                            source=self.provider_name,
                            recorded_at=recorded_at,
                            value=weight,
                            series_type=SeriesType.weight,
                        )
                    )
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to build weight sample: {e}",
                    provider="whoop",
                    task="load_and_save_body_measurement",
                    user_id=str(user_id),
                )

        counts: int = 0
        if samples_to_create:
            counts = timeseries_service.bulk_create_samples(db, samples_to_create)
            db.commit()

        return counts

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
        """Fetch recovery data from Whoop API via v2 endpoint with pagination.

        Returns list of recovery records containing recovery_score, resting_heart_rate,
        hrv_rmssd_milli, spo2_percentage, and skin_temp_celsius.
        """
        return self._fetch_paginated(db, user_id, _RECOVERY_ENDPOINT, start_time, end_time, "recovery")[0]

    def _normalize_recovery_health_score(
        self,
        normalized: dict[str, Any],
        user_id: UUID,
    ) -> HealthScoreCreate | None:
        """Build a HealthScoreCreate for Whoop recovery score."""
        recovery_score = normalized.get("recovery_score")
        timestamp = normalized.get("timestamp")
        if recovery_score is None or timestamp is None:
            return None
        components = {
            k: ScoreComponent(value=normalized.get(k))
            for k in ("resting_heart_rate", "hrv_rmssd_milli", "spo2_percentage", "skin_temp_celsius")
            if normalized.get(k) is not None
        }
        return HealthScoreCreate(
            id=uuid4(),
            user_id=user_id,
            provider=ProviderName.WHOOP,
            category=HealthScoreCategory.RECOVERY,
            value=recovery_score,
            recorded_at=timestamp,
            components=components or None,
        )

    def normalize_recovery(
        self,
        raw_recovery: dict[str, Any],
        user_id: UUID,
    ) -> tuple[dict[str, Any], HealthScoreCreate | None]:  # ty:ignore[invalid-method-override]
        """Normalize Whoop recovery data to our schema.

        Extracts recovery metrics from the score object:
        - recovery_score (0-100)
        - resting_heart_rate (bpm)
        - hrv_rmssd_milli (ms)
        - spo2_percentage (%)
        - skin_temp_celsius (°C)
        """
        cycle_id = raw_recovery.get("cycle_id")
        sleep_id = raw_recovery.get("sleep_id")
        created_at = raw_recovery.get("created_at")
        score_state = raw_recovery.get("score_state")

        # Extract score data (may be None if not scored yet)
        score = raw_recovery.get("score", {}) or {}

        # Only process scored records
        if score_state != "SCORED":
            return {}, None

        # Parse timestamp
        timestamp = None
        if created_at:
            try:
                timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                timestamp = datetime.now(timezone.utc)

        normalized = {
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": timestamp,
            "cycle_id": cycle_id,
            "sleep_id": sleep_id,
            "recovery_score": score.get("recovery_score"),
            "resting_heart_rate": score.get("resting_heart_rate"),
            "hrv_rmssd_milli": score.get("hrv_rmssd_milli"),
            "spo2_percentage": score.get("spo2_percentage"),
            "skin_temp_celsius": score.get("skin_temp_celsius"),
            "raw": raw_recovery,
        }
        return normalized, self._normalize_recovery_health_score(normalized, user_id)

    def save_recovery_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_recovery: dict[str, Any],
    ) -> int:
        """Save normalized recovery data to database as DataPointSeries.

        Saves up to 5 metrics per recovery record:
        - recovery_score
        - resting_heart_rate
        - heart_rate_variability_rmssd (from hrv_rmssd_milli)
        - oxygen_saturation (from spo2_percentage)
        - skin_temperature (from skin_temp_celsius)

        Returns the number of samples saved.
        """
        if not normalized_recovery:
            return 0

        timestamp = normalized_recovery.get("timestamp")
        if not timestamp:
            return 0

        samples_to_create: list[TimeSeriesSampleCreate] = []
        for field_name, series_type in RECOVERY_SERIES.items():
            value = normalized_recovery.get(field_name)
            if value is not None:
                try:
                    samples_to_create.append(
                        TimeSeriesSampleCreate(
                            id=uuid4(),
                            user_id=user_id,
                            source=self.provider_name,
                            recorded_at=timestamp,
                            value=Decimal(str(value)),
                            series_type=series_type,
                        )
                    )
                except Exception as e:
                    log_structured(
                        self.logger,
                        "warning",
                        f"Failed to build recovery sample {field_name}: {e}",
                        provider="whoop",
                        task="save_recovery_data",
                        user_id=str(user_id),
                    )

        counts: int = 0
        if samples_to_create:
            counts = timeseries_service.bulk_create_samples(db, samples_to_create)
            db.commit()

        return counts

    def get_recovery_record(
        self,
        db: DbSession,
        user_id: UUID,
        cycle_id: str,
    ) -> dict[str, Any]:
        """Fetch a single recovery record by cycle_id from /v2/cycle/{cycle_id}/recovery."""
        response = self._make_api_request(db, user_id, f"/v2/cycle/{cycle_id}/recovery")
        store_raw_payload(
            source="api_response",
            provider="whoop",
            payload=response,
            user_id=str(user_id),
            trace_id=f"/v2/cycle/{cycle_id}/recovery",
        )
        return response if isinstance(response, dict) else {}

    def load_single_recovery(
        self,
        db: DbSession,
        user_id: UUID,
        cycle_id: str,
    ) -> int:
        """Fetch a single recovery record by cycle_id, normalize, and save to database."""
        raw = self.get_recovery_record(db, user_id, cycle_id)
        if not raw:
            return 0
        try:
            normalized, health_score = self.normalize_recovery(raw, user_id)
            if not normalized:
                return 0
            count = self.save_recovery_data(db, user_id, normalized)
            if health_score:
                health_score_service.create(db, health_score)
            return count
        except Exception as e:
            log_structured(
                self.logger,
                "warning",
                f"Failed to save recovery record {cycle_id}: {e}",
                provider="whoop",
                task="load_single_recovery",
            )
            return 0

    def load_and_save_recovery(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> tuple[int, bool]:
        """Load recovery data from API and save to database.

        Returns (data point samples saved, partial).
        """
        raw_data, truncated = self._fetch_paginated(db, user_id, _RECOVERY_ENDPOINT, start_time, end_time, "recovery")
        total_count = 0
        health_scores: list[HealthScoreCreate] = []

        for item in raw_data:
            try:
                normalized, health_score = self.normalize_recovery(item, user_id)
                if normalized:  # Skip unscored records
                    total_count += self.save_recovery_data(db, user_id, normalized)
                    if health_score:
                        health_scores.append(health_score)
            except Exception as e:
                db.rollback()
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to save recovery data: {e}",
                    provider="whoop",
                    task="load_and_save_recovery",
                    user_id=str(user_id),
                )

        if health_scores:
            health_score_service.bulk_create(db, health_scores)
            db.commit()

        return total_count, truncated

    # -------------------------------------------------------------------------
    # Cycle Data - Whoop /v2/cycle
    # -------------------------------------------------------------------------

    def get_cycle_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch physiological cycles from Whoop API via v2 endpoint with pagination."""
        return self._fetch_paginated(db, user_id, _CYCLE_ENDPOINT, start_time, end_time, "cycle")[0]

    def get_cycle_record(
        self,
        db: DbSession,
        user_id: UUID,
        cycle_id: str,
    ) -> dict[str, Any]:
        """Fetch a single cycle by its Whoop ID from /v2/cycle/{cycleId}."""
        endpoint = f"{_CYCLE_ENDPOINT}/{cycle_id}"
        response = self._make_api_request(db, user_id, endpoint)
        store_raw_payload(
            source="api_response",
            provider="whoop",
            payload=response,
            user_id=str(user_id),
            trace_id=endpoint,
        )
        return response if isinstance(response, dict) else {}

    def load_single_cycle(
        self,
        db: DbSession,
        user_id: UUID,
        cycle_id: str,
    ) -> int:
        """Fetch one cycle by ID, normalize, and save its energy sample and strain score.

        Driven by sleep.updated: waking is what closes a cycle, so that webhook is the
        only signal Whoop gives that a cycle is final. Whoop emits no cycle event of its
        own, and providers in webhook live_sync_mode are excluded from the periodic pull,
        so without this cycles would only ever land during a historical backfill.

        Returns the number of cycles saved (0 or 1), not the number of rows written.
        """
        raw = self.get_cycle_record(db, user_id, cycle_id)
        if not raw:
            return 0
        try:
            energy_sample, strain_score = self.normalize_cycle(raw, user_id)
            if not energy_sample and not strain_score:
                return 0
            if energy_sample:
                timeseries_service.bulk_create_samples(db, [energy_sample])
            if strain_score:
                health_score_service.bulk_create(db, [strain_score])
            db.commit()
            return 1
        except Exception as e:
            db.rollback()
            log_structured(
                self.logger,
                "warning",
                f"Failed to save cycle {cycle_id}: {e}",
                provider="whoop",
                task="load_single_cycle",
            )
            return 0

    def normalize_cycle(
        self,
        raw_cycle: dict[str, Any],
        user_id: UUID,
    ) -> tuple[TimeSeriesSampleCreate | None, HealthScoreCreate | None]:
        """Normalize one cycle into a daily energy sample and a daily strain score.

        Returns (None, None) for cycles Whoop has not scored yet, and for the one still
        in progress. SCORED does not mean final: Whoop scores the ongoing cycle too, and
        its strain climbs all day. A missing end is what marks it as still running, so
        both checks are needed — health scores are written with on_conflict_do_nothing,
        so an early partial value would win permanently over the real one.
        """
        if raw_cycle.get("score_state") != "SCORED" or not raw_cycle.get("end"):
            return None, None

        score = raw_cycle.get("score") or {}
        start = raw_cycle.get("start")
        if not start:
            return None, None

        try:
            recorded_at = datetime.fromisoformat(start.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None, None

        zone_offset = raw_cycle.get("timezone_offset")
        kilojoule = score.get("kilojoule")
        strain = score.get("strain")

        energy_kcal = kilojoules_to_kcal(kilojoule) if kilojoule is not None else None
        energy_sample = None
        if energy_kcal is not None:
            energy_sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user_id,
                source=self.provider_name,
                recorded_at=recorded_at,
                zone_offset=zone_offset,
                value=energy_kcal,
                series_type=SeriesType.energy,
                is_daily_total=True,
            )

        strain_score = None
        if strain is not None:
            components = {
                k: ScoreComponent(value=score.get(k))
                for k in ("average_heart_rate", "max_heart_rate", "kilojoule")
                if score.get(k) is not None
            }
            strain_score = HealthScoreCreate(
                id=uuid4(),
                user_id=user_id,
                provider=ProviderName.WHOOP,
                category=HealthScoreCategory.STRAIN,
                value=strain,
                recorded_at=recorded_at,
                zone_offset=zone_offset,
                components=components or None,
            )

        return energy_sample, strain_score

    def load_and_save_cycles(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> tuple[int, bool]:
        """Load cycles from API and save daily energy and strain.

        Returns (daily energy samples saved, partial).
        """
        raw_data, truncated = self._fetch_paginated(db, user_id, _CYCLE_ENDPOINT, start_time, end_time, "cycle")
        samples: list[TimeSeriesSampleCreate] = []
        health_scores: list[HealthScoreCreate] = []

        for item in raw_data:
            try:
                energy_sample, strain_score = self.normalize_cycle(item, user_id)
                if energy_sample:
                    samples.append(energy_sample)
                if strain_score:
                    health_scores.append(strain_score)
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to normalize cycle: {e}",
                    provider="whoop",
                    task="load_and_save_cycles",
                    user_id=str(user_id),
                )

        counts: int = 0
        if samples:
            counts = timeseries_service.bulk_create_samples(db, samples)
        if health_scores:
            health_score_service.bulk_create(db, health_scores)
        if samples or health_scores:
            db.commit()

        return counts, truncated

    # -------------------------------------------------------------------------
    # Activity Samples
    # -------------------------------------------------------------------------

    def get_activity_samples(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch activity samples from Whoop API."""
        return []

    def normalize_activity_samples(
        self,
        raw_samples: list[dict[str, Any]],
        user_id: UUID,
    ) -> dict[str, list[dict[str, Any]]]:
        """Normalize activity samples into categorized data."""
        return {}

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
