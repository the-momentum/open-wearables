"""Polar AccessLink v3 247-data implementation.

Phase 1: daily activity summaries — one ``EventRecord`` per day with
``category="daily_activity"``, ``source="polar"``.

Phase 2 (this file now): Sleep Plus Stages and continuous heart rate.
Nightly Recharge remains stubbed for Phase 3.

Endpoint reference: https://www.polar.com/accesslink-api/
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import isodate

from app.config import settings
from app.constants.series_types.polar import POLAR_HYPNOGRAM_MAP
from app.constants.sleep import SleepStageType
from app.database import DbSession
from app.models import EventRecord
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.schemas.enums import SeriesType
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    SleepStage,
    TimeSeriesSampleCreate,
)
from app.schemas.providers.polar import (
    PolarActivityJSON,
    PolarContinuousHRJSON,
    PolarSleepJSON,
    PolarSleepNightsJSON,
)
from app.services.event_record_service import event_record_service
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.timeseries_service import timeseries_service
from app.utils.structured_logging import log_structured


class PolarData247Template(Base247DataTemplate):
    """Polar implementation for 247 data.

    Phase 1 implements `daily_activity` end-to-end. Sleep, recovery, and
    activity_samples are stubbed and return empty collections so the base
    template's `load_all_247_data` remains safe to call.
    """

    def __init__(
        self,
        provider_name: str,
        api_base_url: str,
        oauth: BaseOAuthTemplate,
    ):
        super().__init__(provider_name, api_base_url, oauth)
        self.event_record_repo = EventRecordRepository(EventRecord)
        self.connection_repo = UserConnectionRepository()

    # -------------------------------------------------------------------------
    # HTTP
    # -------------------------------------------------------------------------

    def _make_api_request(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        params: dict[str, Any] | None = None,
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
        )

    # -------------------------------------------------------------------------
    # Daily Activity — Phase 1 (steps / calories / distance)
    # -------------------------------------------------------------------------

    def get_daily_activity_statistics(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch daily activity summaries from Polar AccessLink.

        Polar exposes per-day summaries at `/v3/users/activities/{date}`. We
        iterate day-by-day over the requested window. Days with no data
        return 204 / empty and are silently skipped.
        """
        activities: list[dict[str, Any]] = []
        current = start_date.date()
        last = end_date.date()
        while current <= last:
            endpoint = f"/v3/users/activities/{current.isoformat()}"
            try:
                response = self._make_api_request(db, user_id, endpoint)
                if isinstance(response, dict) and response:
                    activities.append(response)
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Polar daily activity fetch failed for {current}: {e}",
                    provider="polar",
                    task="get_daily_activity_statistics",
                )
            current += timedelta(days=1)
        return activities

    def normalize_daily_activity(
        self,
        raw_stats: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize Polar daily activity to EventRecord + detail payloads."""
        try:
            parsed = PolarActivityJSON.model_validate(raw_stats)
        except Exception as e:
            log_structured(
                self.logger,
                "warning",
                f"Polar daily activity parse failed: {e}",
                provider="polar",
                task="normalize_daily_activity",
            )
            return {}

        start_dt = _parse_polar_datetime(parsed.start_time)
        end_dt = _parse_polar_datetime(parsed.end_time)
        if not (start_dt and end_dt):
            return {}

        duration_seconds = int((end_dt - start_dt).total_seconds())
        record_id = uuid4()
        external_id = start_dt.date().isoformat()

        record = EventRecordCreate(
            id=record_id,
            user_id=user_id,
            category="daily_activity",
            type="polar_daily_summary",
            source_name="Polar AccessLink",
            device_model=None,
            duration_seconds=duration_seconds,
            start_datetime=start_dt,
            end_datetime=end_dt,
            zone_offset=None,
            external_id=external_id,
            source="polar",
        )

        detail = EventRecordDetailCreate(
            record_id=record_id,
            steps_count=parsed.steps,
            energy_burned=Decimal(str(parsed.calories)) if parsed.calories is not None else None,
            distance=Decimal(str(parsed.distance_from_steps)) if parsed.distance_from_steps is not None else None,
        )

        return {"record": record, "detail": detail, "external_id": external_id}

    def save_daily_activity_statistics(
        self,
        db: DbSession,
        user_id: UUID,
        normalized: list[dict[str, Any]],
    ) -> int:
        """Persist normalized daily activity as EventRecord + detail pairs.

        ``event_record_repository.create`` is idempotent on the
        ``(data_source_id, start_datetime, end_datetime)`` unique index — on
        collision it rolls back and returns the existing record — so we trust
        its return value as the authoritative record id and attach the detail
        to that id. Re-syncs of the same day therefore just refresh the detail
        instead of duplicating a row.
        """
        saved = 0
        for item in normalized:
            if not item:
                continue
            record: EventRecordCreate = item["record"]
            detail: EventRecordDetailCreate = item["detail"]

            persisted = event_record_service.create(db, record)
            detail_for_record = detail.model_copy(update={"record_id": persisted.id})
            event_record_service.create_detail(db, detail_for_record, detail_type="workout")
            saved += 1
        return saved

    # -------------------------------------------------------------------------
    # Sleep — Phase 2a (Sleep Plus Stages)
    # -------------------------------------------------------------------------

    def get_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch the last 28 days of sleep nights from Polar AccessLink.

        Polar returns all nights in a single response under ``{"nights": [...]}``
        — start/end times in the method signature exist for base-class
        compatibility but are not used as query params; if a narrower window
        is desired the caller can post-filter by ``date``.
        """
        try:
            response = self._make_api_request(db, user_id, "/v3/users/sleep")
        except Exception as e:
            log_structured(
                self.logger,
                "warning",
                f"Polar sleep fetch failed: {e}",
                provider="polar",
                task="get_sleep_data",
            )
            return []

        if not isinstance(response, dict):
            return []
        nights = response.get("nights", [])
        return nights if isinstance(nights, list) else []

    def normalize_sleep(
        self,
        raw_sleep: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalise a Polar night payload into OW's internal sleep dict shape.

        Mirrors the keys produced by Oura's ``normalize_sleeps`` so the save
        path can stay provider-agnostic.
        """
        try:
            parsed = PolarSleepJSON.model_validate(raw_sleep)
        except Exception as e:
            log_structured(
                self.logger,
                "warning",
                f"Polar sleep parse failed: {e}",
                provider="polar",
                task="normalize_sleep",
            )
            return {}

        start_dt = _parse_polar_datetime(parsed.sleep_start_time)
        end_dt = _parse_polar_datetime(parsed.sleep_end_time)
        if not (start_dt and end_dt):
            log_structured(
                self.logger,
                "warning",
                f"Polar sleep skipped: missing start/end time for date={parsed.date}",
                provider="polar",
                task="normalize_sleep",
            )
            return {}

        duration_seconds = int((end_dt - start_dt).total_seconds())

        stage_intervals = _hypnogram_to_stage_intervals(parsed.hypnogram, start_dt, end_dt)

        return {
            "id": uuid4(),
            "user_id": user_id,
            "provider": self.provider_name,
            "external_id": parsed.date,
            "polar_sleep_date": parsed.date,
            "start_time": start_dt,
            "end_time": end_dt,
            "duration_seconds": duration_seconds,
            "efficiency_percent": float(parsed.sleep_score) if parsed.sleep_score is not None else None,
            "is_nap": False,  # Polar /v3/users/sleep reports primary nightly sleep only
            "stages": {
                "deep_seconds": parsed.deep_sleep or 0,
                "light_seconds": parsed.light_sleep or 0,
                "rem_seconds": parsed.rem_sleep or 0,
                "awake_seconds": parsed.total_interruption_duration or 0,
            },
            "stage_timestamps": stage_intervals,
        }

    def save_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_items: list[dict[str, Any]],
    ) -> int:
        """Persist normalised sleep dicts as ``EventRecord`` + ``SleepDetails``.

        Uses the same ``create_or_merge_sleep`` helper as Oura/Suunto so a
        single night split across multiple devices (or re-syncs) collapses to
        one record.
        """
        count = 0
        for item in normalized_items:
            if not item:
                continue
            sleep_id: UUID = item["id"]
            start_dt: datetime = item["start_time"]
            end_dt: datetime = item["end_time"]

            stages = item.get("stages", {})
            total_sleep_seconds = (
                stages.get("deep_seconds", 0) + stages.get("light_seconds", 0) + stages.get("rem_seconds", 0)
            )
            total_sleep_minutes = total_sleep_seconds // 60
            time_in_bed_minutes = (item.get("duration_seconds") or 0) // 60

            record = EventRecordCreate(
                id=sleep_id,
                user_id=user_id,
                category="sleep",
                type="sleep_session",
                source_name="Polar",
                device_model=None,
                duration_seconds=item.get("duration_seconds"),
                start_datetime=start_dt,
                end_datetime=end_dt,
                zone_offset=None,
                external_id=item.get("external_id"),
                source=self.provider_name,
            )

            detail = EventRecordDetailCreate(
                record_id=sleep_id,
                sleep_total_duration_minutes=total_sleep_minutes,
                sleep_time_in_bed_minutes=time_in_bed_minutes,
                sleep_efficiency_score=(
                    Decimal(str(item["efficiency_percent"]))
                    if item.get("efficiency_percent") is not None
                    else None
                ),
                sleep_deep_minutes=stages.get("deep_seconds", 0) // 60,
                sleep_light_minutes=stages.get("light_seconds", 0) // 60,
                sleep_rem_minutes=stages.get("rem_seconds", 0) // 60,
                sleep_awake_minutes=stages.get("awake_seconds", 0) // 60,
                is_nap=item.get("is_nap", False),
                sleep_stages=item.get("stage_timestamps", []),
            )

            try:
                event_record_service.create_or_merge_sleep(
                    db, user_id, record, detail, settings.sleep_end_gap_minutes
                )
                count += 1
            except Exception as e:
                log_structured(
                    self.logger,
                    "error",
                    f"Polar sleep save failed for {item.get('external_id')}: {e}",
                    provider="polar",
                    task="save_sleep_data",
                )
        return count

    # -------------------------------------------------------------------------
    # Continuous HR — Phase 2b
    # -------------------------------------------------------------------------

    def get_continuous_hr_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch per-date continuous-HR payloads across the window.

        We iterate days rather than using ``/v3/users/continuous-heart-rate``
        with ``from``/``to`` because the per-date endpoint has the same shape
        the daily-activity path uses and is easier to recover day-by-day when
        a single date fails.
        """
        results: list[dict[str, Any]] = []
        current = start_date.date()
        last = end_date.date()
        while current <= last:
            endpoint = f"/v3/users/continuous-heart-rate/{current.isoformat()}"
            try:
                response = self._make_api_request(db, user_id, endpoint)
                if isinstance(response, dict) and response.get("heart_rate_samples"):
                    results.append(response)
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Polar continuous HR fetch failed for {current}: {e}",
                    provider="polar",
                    task="get_continuous_hr_data",
                )
            current += timedelta(days=1)
        return results

    def normalize_continuous_hr(
        self,
        raw_days: list[dict[str, Any]],
        user_id: UUID,
    ) -> list[TimeSeriesSampleCreate]:
        """Convert per-date payloads into bulk-insertable timeseries samples."""
        samples: list[TimeSeriesSampleCreate] = []
        for raw in raw_days:
            try:
                parsed = PolarContinuousHRJSON.model_validate(raw)
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Polar continuous HR parse failed: {e}",
                    provider="polar",
                    task="normalize_continuous_hr",
                )
                continue

            try:
                day = datetime.strptime(parsed.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            for s in parsed.heart_rate_samples:
                recorded_at = _combine_date_time(day, s.sample_time)
                if recorded_at is None:
                    continue
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        value=Decimal(str(s.heart_rate)),
                        series_type=SeriesType.heart_rate,
                    )
                )
        return samples

    def save_continuous_hr(
        self,
        db: DbSession,
        user_id: UUID,  # kept for signature symmetry with Oura/Suunto
        samples: list[TimeSeriesSampleCreate],
    ) -> int:
        if samples:
            timeseries_service.bulk_create_samples(db, samples)
        return len(samples)

    # -------------------------------------------------------------------------
    # Recovery / Activity Samples — Phase 3 stubs (base-class compatibility)
    # -------------------------------------------------------------------------

    def get_recovery_data(self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime) -> list[dict[str, Any]]:
        return []

    def normalize_recovery(self, raw_recovery: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        return {}

    def get_activity_samples(self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime) -> list[dict[str, Any]]:
        return []

    def normalize_activity_samples(self, raw_samples: list[dict[str, Any]], user_id: UUID) -> dict[str, list[dict[str, Any]]]:
        return {}

    # -------------------------------------------------------------------------
    # Save aggregator — called by sync_vendor_data_task.load_and_save_all branch
    # -------------------------------------------------------------------------

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        is_first_sync: bool = False,
    ) -> dict[str, int]:
        """Run all Phase 1 + Phase 2 Polar syncs in one pass."""
        end_dt = end_time or datetime.now(timezone.utc)
        start_dt = start_time or (end_dt - timedelta(days=28 if is_first_sync else 7))

        results: dict[str, int] = {
            "daily_activity_synced": 0,
            "sleep_sessions_synced": 0,
            "continuous_hr_synced": 0,
            "nightly_recharge_synced": 0,  # Phase 3
        }

        # Each data type runs in its own try block and rolls back on failure
        # so a DB error in one path doesn't poison the SQLAlchemy session for
        # the next — tests for this session-isolation contract live in
        # test_polar_247_sync_isolation.py.

        # Daily activity (Phase 1)
        try:
            raw_daily = self.get_daily_activity_statistics(db, user_id, start_dt, end_dt)
            normalized = [self.normalize_daily_activity(item, user_id) for item in raw_daily]
            results["daily_activity_synced"] = self.save_daily_activity_statistics(db, user_id, normalized)
        except Exception as e:
            db.rollback()
            log_structured(
                self.logger,
                "error",
                f"Polar daily activity sync failed: {e}",
                provider="polar",
                task="load_and_save_all",
            )

        # Sleep (Phase 2a)
        try:
            raw_nights = self.get_sleep_data(db, user_id, start_dt, end_dt)
            normalized_sleep = [self.normalize_sleep(n, user_id) for n in raw_nights]
            results["sleep_sessions_synced"] = self.save_sleep_data(db, user_id, normalized_sleep)
        except Exception as e:
            db.rollback()
            log_structured(
                self.logger,
                "error",
                f"Polar sleep sync failed: {e}",
                provider="polar",
                task="load_and_save_all",
            )

        # Continuous HR (Phase 2b)
        try:
            raw_hr = self.get_continuous_hr_data(db, user_id, start_dt, end_dt)
            samples = self.normalize_continuous_hr(raw_hr, user_id)
            results["continuous_hr_synced"] = self.save_continuous_hr(db, user_id, samples)
        except Exception as e:
            db.rollback()
            log_structured(
                self.logger,
                "error",
                f"Polar continuous HR sync failed: {e}",
                provider="polar",
                task="load_and_save_all",
            )

        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_polar_datetime(value: str | None) -> datetime | None:
    """Parse Polar AccessLink ISO-8601 datetime, tolerating missing timezone.

    Polar's v3 responses sometimes omit the TZ (wall-clock local time). We
    treat naive values as UTC so downstream aware/naive comparisons don't
    crash. Display-side code should convert to the user's timezone.
    """
    if not value:
        return None
    try:
        dt = isodate.parse_datetime(value)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _combine_date_time(day: datetime, sample_time: str | None) -> datetime | None:
    """Combine a ``YYYY-MM-DD`` day (as aware datetime) with ``HH:MM[:SS]``."""
    if not sample_time:
        return None
    parts = sample_time.split(":")
    try:
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        s = int(parts[2]) if len(parts) > 2 else 0
    except (ValueError, IndexError):
        return None
    return day.replace(hour=h, minute=m, second=s, microsecond=0)


def _hypnogram_to_stage_intervals(
    hypnogram: dict[str, int] | None,
    sleep_start: datetime,
    sleep_end: datetime,
) -> list[SleepStage]:
    """Convert Polar's ``{"HH:MM": stage_code}`` transition map into intervals.

    Each key marks when that stage begins; duration runs until the next key,
    or ``sleep_end`` for the final interval. Transitions are anchored to
    ``sleep_start``'s calendar date and bumped by one day whenever they would
    regress past the previous transition (e.g. nights that cross midnight).
    """
    if not hypnogram:
        return []

    base_date = sleep_start.date()
    tzinfo = sleep_start.tzinfo

    transitions: list[tuple[datetime, int]] = []
    prev_dt: datetime | None = None
    for hhmm, code in sorted(hypnogram.items()):
        try:
            parts = hhmm.split(":")
            h, m = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            continue
        candidate = datetime(base_date.year, base_date.month, base_date.day, h, m, tzinfo=tzinfo)
        while prev_dt is not None and candidate <= prev_dt:
            candidate += timedelta(days=1)
        transitions.append((candidate, code))
        prev_dt = candidate

    intervals: list[SleepStage] = []
    for i, (start_dt, code) in enumerate(transitions):
        end_dt = transitions[i + 1][0] if i + 1 < len(transitions) else sleep_end
        if end_dt <= start_dt:
            continue
        stage = POLAR_HYPNOGRAM_MAP.get(code, SleepStageType.UNKNOWN)
        intervals.append(SleepStage(stage=stage, start_time=start_dt, end_time=end_dt))
    return intervals
