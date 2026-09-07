"""Ultrahuman Ring Air 24/7 data implementation for sleep, recovery, and activity samples."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.config import settings
from app.constants.sleep import SleepStageType
from app.database import DbSession
from app.models import EventRecord
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.repositories.data_point_series_repository import WriteCounts
from app.schemas.enums import daily_total_flag
from app.schemas.enums.series_types import SeriesType
from app.schemas.model_crud.activities.data_point_series import TimeSeriesSampleCreate
from app.schemas.model_crud.activities.event_record import EventRecordCreate
from app.schemas.model_crud.activities.event_record_detail import EventRecordDetailCreate
from app.schemas.model_crud.activities.sleep import SleepStage
from app.services.event_record_service import event_record_service
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.sync_247_result import Sync247Result, Sync247Run
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.ultrahuman.coverage import ACTIVITY_SAMPLE_SERIES
from app.services.raw_payload_storage import store_raw_payload
from app.services.timeseries_service import timeseries_service
from app.utils.structured_logging import log_structured

# Ultrahuman sleep_graph.data stage names → our canonical SleepStageType.
SLEEP_GRAPH_STAGE_MAP: dict[str, SleepStageType] = {
    "deep_sleep": SleepStageType.DEEP,
    "light_sleep": SleepStageType.LIGHT,
    "rem_sleep": SleepStageType.REM,
    "awake": SleepStageType.AWAKE,
}


class Ultrahuman247Data(Base247DataTemplate):
    """Ultrahuman Ring Air implementation for 24/7 data (sleep, recovery, activity)."""

    def __init__(
        self,
        provider_name: str,
        api_base_url: str,
        oauth: BaseOAuthTemplate,
    ) -> None:
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
        """Fetch all metrics for a specific day from Ultrahuman API.

        Returns:
            list[dict[str, Any]]: List of metrics for the day, or empty list on recoverable errors.

        Raises:
            HTTPException: For fatal errors (401, 403) that require token refresh/invalidate connection.
        """
        date_str = date.strftime("%Y-%m-%d")
        try:
            response = self._make_api_request(
                db,
                user_id,
                "/user_data/metrics",
                params={"date": date_str},
            )
            store_raw_payload(
                source="api_response",
                provider="ultrahuman",
                payload=response,
                user_id=str(user_id),
                trace_id=date_str,
            )
            if response and "data" in response and "metric_data" in response["data"]:
                # Add date to each metric item for reference
                metrics = response["data"]["metric_data"]
                for item in metrics:
                    item["date"] = date_str
                    # Inject date into the inner object for use in normalization
                    if "object" in item and isinstance(item["object"], dict):
                        item["object"]["ultrahuman_date"] = date_str
                return metrics
        except HTTPException as e:
            # Fatal errors - should be raised to trigger token refresh or invalidate connection
            if e.status_code in (401, 403):
                log_structured(
                    self.logger,
                    "error",
                    "Authorization failed while fetching daily metrics",
                    provider="ultrahuman",
                    task="fetch_daily_metrics",
                    date=date_str,
                    status_code=e.status_code,
                    error=e.detail,
                )
                raise
            # Recoverable errors - log and continue with next day
            log_structured(
                self.logger,
                "warning",
                "API error while fetching daily metrics",
                provider="ultrahuman",
                task="fetch_daily_metrics",
                date=date_str,
                status_code=e.status_code,
                error=e.detail,
            )
            return []
        except Exception as e:
            # Network errors and other unexpected errors - log and continue
            log_structured(
                self.logger,
                "warning",
                "Failed to fetch daily metrics",
                provider="ultrahuman",
                task="fetch_daily_metrics",
                date=date_str,
                error=str(e),
            )
            return []

        return []

    # -------------------------------------------------------------------------
    # Sleep Data
    # -------------------------------------------------------------------------

    @staticmethod
    def _normalize_sleep_stages(raw_sleep: dict[str, Any]) -> list[SleepStage]:
        """Parse the ``sleep_graph.data`` interval timeline into canonical SleepStage objects.

        Ultrahuman returns timestamped stage transitions as
        ``{"start": <unix>, "end": <unix>, "type": "deep_sleep", ...}``. Unknown stage
        names fall back to ``SleepStageType.UNKNOWN``; intervals missing start/end are skipped.
        """
        graph = raw_sleep.get("sleep_graph") or {}
        intervals = graph.get("data", []) if isinstance(graph, dict) else []

        stages: list[SleepStage] = []
        for interval in intervals:
            start_ts = interval.get("start")
            end_ts = interval.get("end")
            if start_ts is None or end_ts is None:
                continue
            stages.append(
                SleepStage(
                    stage=SLEEP_GRAPH_STAGE_MAP.get(interval.get("type"), SleepStageType.UNKNOWN),
                    start_time=datetime.fromtimestamp(start_ts, tz=timezone.utc),
                    end_time=datetime.fromtimestamp(end_ts, tz=timezone.utc),
                )
            )

        stages.sort(key=lambda s: s.start_time)
        return stages

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
            "stage_timestamps": self._normalize_sleep_stages(raw_sleep),
            "ultrahuman_date": date_str,
            "raw": raw_sleep,
        }

    def save_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_sleep: dict[str, Any],
    ) -> bool:
        """Save normalized sleep data to database as EventRecord with SleepDetails.

        Returns True if the record was saved, False if skipped.
        """
        sleep_id = normalized_sleep["id"]
        start_dt = normalized_sleep.get("start_time")
        end_dt = normalized_sleep.get("end_time")

        if not start_dt or not end_dt:
            log_structured(
                self.logger,
                "warning",
                "Skipping sleep record: missing start/end time",
                provider="ultrahuman",
                task="save_sleep_data",
                sleep_id=str(sleep_id),
                user_id=str(user_id),
            )
            return False

        # Create EventRecord for sleep
        record = EventRecordCreate(
            id=sleep_id,
            category="sleep",
            type="sleep_session",
            source_name="Ultrahuman Ring Air",
            duration_seconds=normalized_sleep.get("duration_seconds"),
            start_datetime=start_dt,
            end_datetime=end_dt,
            external_id=f"sleep-{normalized_sleep.get('ultrahuman_date')}",
            provider=self.provider_name,
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
            sleep_stages=normalized_sleep.get("stage_timestamps") or None,
        )

        try:
            event_record_service.create_or_merge_sleep(db, user_id, record, detail, settings.sleep_end_gap_minutes)
            return True
        except Exception as e:
            log_structured(
                self.logger,
                "error",
                "Error saving sleep record",
                provider="ultrahuman",
                task="save_sleep_data",
                sleep_id=str(sleep_id),
                user_id=str(user_id),
                error=str(e),
            )
            return False

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
        raw_samples: list[dict[str, Any]],
        user_id: UUID,
    ) -> dict[str, list[dict[str, Any]]]:
        """Normalize activity samples into categorized data.

        raw_samples: List of sample dictionaries with type and values
        """
        result = {
            "heart_rate": [],
            "hrv": [],
            "temperature": [],
            "steps": [],
        }

        for sample in raw_samples:
            sample_type = sample.get("type")

            if sample_type == "hr":
                values = sample.get("values", [])
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

            elif sample_type == "hrv":
                values = sample.get("values", [])
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

            elif sample_type == "temp":
                values = sample.get("values", [])
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

            elif sample_type == "steps":
                values = sample.get("values", [])
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

    def _build_activity_samples(
        self,
        user_id: UUID,
        normalized_samples: dict[str, list[dict[str, Any]]],
    ) -> list[TimeSeriesSampleCreate]:
        """Build TimeSeriesSampleCreate rows from normalized activity samples (HR, HRV, etc.).

        The rows are persisted in bulk by the caller via
        ``timeseries_service.bulk_create_samples`` (upsert), not written here.
        """
        samples: list[TimeSeriesSampleCreate] = []

        for key, entries in normalized_samples.items():
            series_type = ACTIVITY_SAMPLE_SERIES.get(key)
            if not series_type:
                continue

            for sample in entries:
                recorded_at_str = sample.get("recorded_at")
                if not recorded_at_str:
                    continue
                try:
                    recorded_at = datetime.fromisoformat(recorded_at_str.replace("Z", "+00:00"))
                    samples.append(
                        TimeSeriesSampleCreate(
                            id=uuid4(),
                            user_id=user_id,
                            provider=self.provider_name,
                            recorded_at=recorded_at,
                            value=Decimal(str(sample.get("value"))),
                            series_type=series_type,
                            is_daily_total=daily_total_flag(series_type, is_daily=False),
                        )
                    )
                except Exception as e:
                    log_structured(
                        self.logger,
                        "warning",
                        "Failed to build activity sample",
                        provider="ultrahuman",
                        task="build_activity_samples",
                        series=key,
                        user_id=str(user_id),
                        recorded_at=recorded_at_str or "unknown time",
                        error=str(e),
                    )

        return samples

    # -------------------------------------------------------------------------
    # Combined Load (Main Entry Point)
    # -------------------------------------------------------------------------

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        is_first_sync: bool = False,
    ) -> Sync247Result:
        """Load and save all 247 data types by fetching daily metrics.

        Ultrahuman exposes one metrics endpoint per day, so the window is walked
        a day at a time and each data type's counts accumulate across days. A
        fatal auth error (401/403) aborts the whole run; anything else is
        recorded against the data type it belongs to and the walk continues.
        """

        # TODO: Extract default backfill days (30) to an env var / settings constant.
        # Not doing it now - this should be unified across all providers at once,
        # since other providers like Garmin, Oura, Whoop each hardcode their own defaults.

        start_time, end_time = self.resolve_window(start_time, end_time)

        # HTTPException from _fetch_daily_metrics (401/403) invalidates every remaining
        # day, so it propagates instead of being recorded against one data type.
        run = self.sync_run(db, user_id, fatal=(HTTPException,))
        run.expect("sleep", "activity_samples")

        current_date = datetime.combine(start_time.date(), datetime.min.time(), tzinfo=timezone.utc)
        end_date = datetime.combine(end_time.date(), datetime.min.time(), tzinfo=timezone.utc)
        while current_date <= end_date:
            items_by_type = self._fetch_items_by_type(db, user_id, current_date, run)

            if "Sleep" in items_by_type:
                with run.step("sleep", accumulate=True, rollback_on_error=False) as step:
                    normalized_sleep = self.normalize_sleep(items_by_type["Sleep"], user_id)
                    step.record(1 if self.save_sleep_data(db, user_id, normalized_sleep) else 0)

            # Recovery is fetched but not persisted: there is no daily-recovery table yet,
            # and EventRecord has no type that fits generic daily recovery metrics.

            with run.step("activity_samples", accumulate=True, commit=True) as step:
                step.record(self._save_daily_activity(db, user_id, items_by_type))

            current_date += timedelta(days=1)

        run.log_summary()
        return run.result

    def _fetch_items_by_type(
        self,
        db: DbSession,
        user_id: UUID,
        day: datetime,
        run: Sync247Run,
    ) -> dict[str, Any]:
        """Fetch one day of metrics, keyed by Ultrahuman's type name.

        The fetch feeds every data type, so a failure is recorded against the
        endpoint rather than any one of them, and the day is skipped.
        """
        try:
            metrics_list = self._fetch_daily_metrics(db, user_id, day)
        except HTTPException:
            raise
        except Exception as e:
            run.fail("daily_metrics", e)
            return {}

        return {item["type"]: item["object"] for item in metrics_list if item.get("type") and "object" in item}

    def _save_daily_activity(
        self,
        db: DbSession,
        user_id: UUID,
        items_by_type: dict[str, Any],
    ) -> WriteCounts:
        """Persist one day's activity series plus its single-value daily metrics."""
        sample_inputs = [
            {"type": t, "values": items_by_type[t].get("values", [])}
            for t in ("hr", "hrv", "temp", "steps")
            if t in items_by_type
        ]
        samples: list[TimeSeriesSampleCreate] = []
        if sample_inputs:
            samples.extend(
                self._build_activity_samples(user_id, self.normalize_activity_samples(sample_inputs, user_id))
            )

        # vo2_max and active_minutes are single daily values rather than series.
        for item_type, series_type, is_daily_total in (
            ("vo2_max", SeriesType.vo2_max, False),
            ("active_minutes", SeriesType.active_time, True),
        ):
            obj = items_by_type.get(item_type)
            if not obj:
                continue
            value = obj.get("value")
            timestamp = obj.get("day_start_timestamp")
            if value is None or not timestamp:
                continue
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider=self.provider_name,
                    recorded_at=datetime.fromtimestamp(timestamp, tz=timezone.utc),
                    value=Decimal(str(value)),
                    series_type=series_type,
                    is_daily_total=is_daily_total,
                )
            )

        if not samples:
            return WriteCounts(0, 0)
        return timeseries_service.bulk_create_samples(db, samples)

    # -------------------------------------------------------------------------
    # Abstract Method Implementations
    # -------------------------------------------------------------------------

    def get_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch sleep data from provider API for a date range.

        Returns:
            list[dict[str, Any]]: List of sleep data objects from API.
        """
        sleep_data = []
        current_date = start_time.date()
        end_date = end_time.date()

        while current_date <= end_date:
            metrics_list = self._fetch_daily_metrics(db, user_id, datetime.combine(current_date, datetime.min.time()))
            date_str = current_date.strftime("%Y-%m-%d")

            for item in metrics_list:
                if item.get("type") == "Sleep" and "object" in item:
                    item["object"]["ultrahuman_date"] = date_str
                    sleep_data.append(item["object"])

            current_date = current_date + timedelta(days=1)

        return sleep_data

    def get_recovery_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch recovery data from provider API for a date range.

        Returns:
            list[dict[str, Any]]: List of recovery data objects from API.
        """
        recovery_data = []
        current_date = start_time.date()
        end_date = end_time.date()

        while current_date <= end_date:
            metrics_list = self._fetch_daily_metrics(db, user_id, datetime.combine(current_date, datetime.min.time()))
            date_str = current_date.strftime("%Y-%m-%d")

            for item in metrics_list:
                item_type = item.get("type")
                if item_type in ("recovery_index", "movement_index", "metabolic_score") and "object" in item:
                    item["object"]["ultrahuman_date"] = date_str
                    recovery_data.append(item["object"])

            current_date = current_date + timedelta(days=1)

        return recovery_data

    def get_activity_samples(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch activity samples (HR, steps, SpO2) from provider API for a date range.

        Returns:
            list[dict[str, Any]]: List of activity sample objects from API.
        """
        samples = []
        current_date = start_time.date()
        end_date = end_time.date()

        while current_date <= end_date:
            metrics_list = self._fetch_daily_metrics(db, user_id, datetime.combine(current_date, datetime.min.time()))
            date_str = current_date.strftime("%Y-%m-%d")

            for item in metrics_list:
                item_type = item.get("type")
                if item_type in ("hr", "hrv", "temp", "steps") and "object" in item:
                    item["object"]["ultrahuman_date"] = date_str
                    samples.append({"type": item_type, "object": item["object"]})

            current_date = current_date + timedelta(days=1)

        return samples

    def get_daily_activity_statistics(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch aggregated daily activity statistics.

        Ultrahuman does not provide daily activity statistics endpoint.

        Returns:
            list[dict[str, Any]]: Empty list as this is not available.
        """
        return []

    def normalize_daily_activity(
        self,
        raw_stats: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize daily activity statistics to our schema.

        Ultrahuman does not provide daily activity statistics.

        Returns:
            dict[str, Any]: Empty dict as this is not available.
        """
        return {}
