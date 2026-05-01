"""Withings 24/7 data sync — sleep summaries + body composition.

**Phase B scope:** sleep nightly summaries (one EventRecord per night) and
body composition / weight samples (one DataPointSeries per measurement).

**Phase C deferred:** recovery score (Withings has no direct analog —
sleep_score may proxy later), per-minute heart-rate stream
(``/v2/heart action=list``), per-minute activity samples
(``/v2/measure action=getintradayactivity``), and daily activity totals
(``/v2/measure action=getactivity``). The four required-by-base methods
for those domains are still stubbed to return empty results so the
celery sync task completes cleanly.

Reference implementation: ``app/services/providers/whoop/data_247.py``.
Differences:
- Withings sleep durations are SECONDS (not milliseconds like Whoop).
- Sleep summary IDs are int (not UUID) — we mint a uuid4 internal ID and
  store the Withings int as ``external_id``.
- Body measurements are POST to ``/measure action=getmeas`` instead of a
  single REST GET; we handle multiple measurements per group.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.config import settings
from app.database import DbSession
from app.models import DataSource, EventRecord
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas.enums import SeriesType
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    TimeSeriesSampleCreate,
)
from app.schemas.providers.withings import (
    WithingsMeasureGetmeasResponse,
    WithingsSleepGetsummaryResponse,
)
from app.services.event_record_service import event_record_service
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.withings.withings_api_client import post_withings_action
from app.services.raw_payload_storage import store_raw_payload
from app.services.timeseries_service import timeseries_service
from app.utils.structured_logging import log_structured

# Withings measure type integer → (SeriesType, value scale multiplier).
# Withings returns values as ``raw * 10**unit``; the multiplier here is
# applied AFTER that conversion to handle unit mismatches between Withings
# and our canonical schema (e.g. height: m → cm).
#
# Type 88 (bone mass) is intentionally absent — no SeriesType match yet.
WITHINGS_MEASURE_TYPE_MAP: dict[int, tuple[SeriesType, Decimal]] = {
    1: (SeriesType.weight, Decimal("1")),                 # kg → kg
    4: (SeriesType.height, Decimal("100")),               # m → cm
    5: (SeriesType.lean_body_mass, Decimal("1")),         # kg → kg
    6: (SeriesType.body_fat_percentage, Decimal("1")),    # already %
    8: (SeriesType.body_fat_mass, Decimal("1")),          # kg → kg
    11: (SeriesType.resting_heart_rate, Decimal("1")),    # bpm → bpm
    76: (SeriesType.skeletal_muscle_mass, Decimal("1")),  # kg → kg
    77: (SeriesType.hydration, Decimal("1")),             # kg → kg
}


class Withings247Data(Base247DataTemplate):
    """Withings 24/7 data implementation (sleep + body comp)."""

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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _post(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        action: str,
        params: dict[str, Any] | None = None,
    ) -> dict:
        """Thin wrapper around post_withings_action threading repos + oauth."""
        return post_withings_action(
            db=db,
            user_id=user_id,
            connection_repo=self.connection_repo,
            oauth=self.oauth,
            api_base_url=self.api_base_url,
            endpoint=endpoint,
            action=action,
            params=params,
        )

    def _epoch_to_dt(self, epoch_seconds: int) -> datetime:
        return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)

    # ------------------------------------------------------------------
    # Sleep — POST /v2/sleep action=getsummary
    # ------------------------------------------------------------------

    def get_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch sleep summaries from Withings, paginated via more/offset."""
        all_records: list[dict[str, Any]] = []
        offset: int | None = None
        # Withings expects YYYY-MM-DD in user's timezone for getsummary.
        start_ymd = start_time.astimezone(timezone.utc).strftime("%Y-%m-%d")
        end_ymd = end_time.astimezone(timezone.utc).strftime("%Y-%m-%d")

        # Withings only returns explicitly-requested fields in `data`.
        data_fields = ",".join([
            "wakeupduration",
            "lightsleepduration",
            "deepsleepduration",
            "remsleepduration",
            "durationtosleep",
            "durationtowakeup",
            "wakeupcount",
            "hr_average",
            "hr_min",
            "hr_max",
            "rr_average",
            "rr_min",
            "rr_max",
            "sleep_score",
            "breathing_disturbances_intensity",
            "snoring",
            "snoringepisodecount",
        ])

        while True:
            params: dict[str, Any] = {
                "startdateymd": start_ymd,
                "enddateymd": end_ymd,
                "data_fields": data_fields,
            }
            if offset is not None:
                params["offset"] = offset

            try:
                body = self._post(db, user_id, "/v2/sleep", "getsummary", params=params)
            except Exception as e:
                log_structured(
                    self.logger, "error",
                    f"Error fetching Withings sleep summaries: {e}",
                    provider="withings", task="get_sleep_data", user_id=str(user_id),
                )
                if all_records:
                    break
                raise

            store_raw_payload(
                source="api_response", provider="withings", payload=body,
                user_id=str(user_id), trace_id="/v2/sleep:getsummary",
            )

            try:
                parsed = WithingsSleepGetsummaryResponse(**body)
            except Exception as e:
                log_structured(
                    self.logger, "warning",
                    f"Withings sleep response did not validate: {e}",
                    provider="withings", task="get_sleep_data", user_id=str(user_id),
                )
                break

            all_records.extend([s.model_dump() for s in parsed.series])

            if not parsed.more or parsed.offset is None:
                break
            offset = parsed.offset

        return all_records

    def normalize_sleep(
        self,
        raw_sleep: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize a single Withings sleep summary into our schema."""
        external_id = raw_sleep.get("id")
        startdate = raw_sleep.get("startdate")
        enddate = raw_sleep.get("enddate")
        timezone_str = raw_sleep.get("timezone")
        data = raw_sleep.get("data", {}) or {}

        deep_s = int(data.get("deepsleepduration") or 0)
        light_s = int(data.get("lightsleepduration") or 0)
        rem_s = int(data.get("remsleepduration") or 0)
        awake_s = int(data.get("wakeupduration") or 0)

        total_in_bed_s = (
            (enddate - startdate)
            if isinstance(startdate, int) and isinstance(enddate, int)
            else (deep_s + light_s + rem_s + awake_s)
        )

        return {
            "id": uuid4(),
            "user_id": user_id,
            "provider": self.provider_name,
            "external_id": str(external_id) if external_id is not None else None,
            "startdate": startdate,
            "enddate": enddate,
            # Withings gives a tz NAME (e.g. "America/New_York"), not an offset
            # — leave zone_offset null since the schema expects "+/-HH:MM".
            "zone_offset": None,
            "timezone_name": timezone_str,
            "duration_seconds": total_in_bed_s,
            "stages": {
                "deep_seconds": deep_s,
                "light_seconds": light_s,
                "rem_seconds": rem_s,
                "awake_seconds": awake_s,
            },
            "sleep_score": data.get("sleep_score"),
        }

    def save_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized: dict[str, Any],
    ) -> None:
        """Persist a normalized Withings sleep summary as an EventRecord+Detail."""
        startdate = normalized.get("startdate")
        enddate = normalized.get("enddate")
        if not isinstance(startdate, int) or not isinstance(enddate, int):
            log_structured(
                self.logger, "warning",
                f"Skipping Withings sleep record {normalized.get('external_id')}: "
                "missing startdate/enddate",
                provider="withings", task="save_sleep_data", user_id=str(user_id),
            )
            return

        sleep_id = normalized["id"]
        start_dt = self._epoch_to_dt(startdate)
        end_dt = self._epoch_to_dt(enddate)
        duration_s = normalized.get("duration_seconds") or int((end_dt - start_dt).total_seconds())

        record = EventRecordCreate(
            id=sleep_id,
            category="sleep",
            type="sleep_session",
            source_name="Withings",
            device_model=None,
            duration_seconds=duration_s,
            start_datetime=start_dt,
            end_datetime=end_dt,
            zone_offset=normalized.get("zone_offset"),
            external_id=normalized.get("external_id"),
            source=self.provider_name,
            user_id=user_id,
        )

        stages = normalized.get("stages", {})
        deep_s = stages.get("deep_seconds", 0)
        light_s = stages.get("light_seconds", 0)
        rem_s = stages.get("rem_seconds", 0)
        awake_s = stages.get("awake_seconds", 0)
        total_sleep_s = deep_s + light_s + rem_s

        detail = EventRecordDetailCreate(
            record_id=sleep_id,
            sleep_total_duration_minutes=total_sleep_s // 60,
            sleep_time_in_bed_minutes=duration_s // 60,
            sleep_deep_minutes=deep_s // 60,
            sleep_light_minutes=light_s // 60,
            sleep_rem_minutes=rem_s // 60,
            sleep_awake_minutes=awake_s // 60,
            is_nap=False,
        )

        try:
            event_record_service.create_or_merge_sleep(
                db, user_id, record, detail, settings.sleep_end_gap_minutes,
            )
        except Exception as e:
            log_structured(
                self.logger, "error",
                f"Error saving Withings sleep record {normalized.get('external_id')}: {e}",
                provider="withings", task="save_sleep_data", user_id=str(user_id),
            )

    def load_and_save_sleep(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        raw_data = self.get_sleep_data(db, user_id, start_time, end_time)
        count = 0
        for item in raw_data:
            try:
                normalized = self.normalize_sleep(item, user_id)
                self.save_sleep_data(db, user_id, normalized)
                count += 1
            except Exception as e:
                log_structured(
                    self.logger, "warning",
                    f"Failed to save Withings sleep summary: {e}",
                    provider="withings", task="load_and_save_sleep", user_id=str(user_id),
                )
        return count

    # ------------------------------------------------------------------
    # Body composition — POST /measure action=getmeas
    # ------------------------------------------------------------------

    def get_body_measurements(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, Any]:
        """Fetch body-composition measurements from Withings.

        Returns a dict with key ``measuregrps`` (list of group dicts).
        Pagination via more/offset is supported.
        """
        meastypes = ",".join(str(t) for t in WITHINGS_MEASURE_TYPE_MAP.keys())
        startdate = int(start_time.astimezone(timezone.utc).timestamp())
        enddate = int(end_time.astimezone(timezone.utc).timestamp())

        all_groups: list[dict[str, Any]] = []
        offset: int | None = None
        while True:
            params: dict[str, Any] = {
                "meastypes": meastypes,
                "startdate": startdate,
                "enddate": enddate,
                "category": 1,  # 1 = real measurements (not user objectives)
            }
            if offset is not None:
                params["offset"] = offset

            try:
                body = self._post(db, user_id, "/measure", "getmeas", params=params)
            except Exception as e:
                log_structured(
                    self.logger, "error",
                    f"Error fetching Withings body measurements: {e}",
                    provider="withings", task="get_body_measurements", user_id=str(user_id),
                )
                if all_groups:
                    break
                raise

            store_raw_payload(
                source="api_response", provider="withings", payload=body,
                user_id=str(user_id), trace_id="/measure:getmeas",
            )

            try:
                parsed = WithingsMeasureGetmeasResponse(**body)
            except Exception as e:
                log_structured(
                    self.logger, "warning",
                    f"Withings measure response did not validate: {e}",
                    provider="withings", task="get_body_measurements", user_id=str(user_id),
                )
                break

            all_groups.extend([g.model_dump() for g in parsed.measuregrps])

            if not parsed.more or parsed.offset is None:
                break
            offset = parsed.offset

        return {"measuregrps": all_groups}

    def load_and_save_body_measurement(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Persist body-comp measurements as DataPointSeries rows.

        Each Withings measurement carries its own timestamp from the device,
        so we record every one — dedup is handled by the unique index
        ``(data_source_id, series_type_definition_id, recorded_at)``.
        """
        body = self.get_body_measurements(db, user_id, start_time, end_time)
        groups = body.get("measuregrps", []) if isinstance(body, dict) else []

        samples: list[TimeSeriesSampleCreate] = []
        for group in groups:
            recorded_at = group.get("date")
            if not isinstance(recorded_at, int):
                continue
            recorded_dt = self._epoch_to_dt(recorded_at)
            for measure in group.get("measures", []) or []:
                m_type = measure.get("type")
                m_value = measure.get("value")
                m_unit = measure.get("unit")
                if m_type is None or m_value is None or m_unit is None:
                    continue
                mapping = WITHINGS_MEASURE_TYPE_MAP.get(int(m_type))
                if mapping is None:
                    continue  # type we don't store (e.g. bone mass)
                series_type, scale = mapping
                # value = raw * 10**unit, then scale (e.g. m→cm).
                try:
                    physical = Decimal(int(m_value)) * (Decimal(10) ** int(m_unit))
                    final_value = physical * scale
                except Exception:
                    continue
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        provider=self.provider_name,
                        source=self.provider_name,
                        recorded_at=recorded_dt,
                        value=final_value,
                        series_type=series_type,
                        external_id=str(group.get("grpid")) if group.get("grpid") is not None else None,
                    )
                )

        if not samples:
            return 0

        # bulk_create_samples queues INSERT statements on the session but does
        # NOT commit (per the repo-layer comment "Caller should commit").
        # Without an explicit commit here, the celery task's `with SessionLocal()`
        # context closes uncommitted and rolls back the whole batch.
        try:
            timeseries_service.bulk_create_samples(db, samples)
            db.commit()
            return len(samples)
        except Exception as e:
            db.rollback()
            log_structured(
                self.logger, "warning",
                f"bulk_create_samples failed for Withings body comp ({e}); "
                "falling back to per-sample inserts",
                provider="withings",
                task="load_and_save_body_measurement",
                user_id=str(user_id),
            )
            inserted = 0
            for s in samples:
                try:
                    timeseries_service.bulk_create_samples(db, [s])
                    db.commit()
                    inserted += 1
                except Exception:
                    db.rollback()
            return inserted

    # ------------------------------------------------------------------
    # Recovery / activity samples / daily activity — Phase C deferred
    # ------------------------------------------------------------------

    def get_recovery_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        return []

    def normalize_recovery(self, raw_recovery: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        # Unreachable in Phase B (get_recovery_data returns []).
        raise NotImplementedError("Withings recovery normalization — Phase C")

    def get_activity_samples(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        return []

    def normalize_activity_samples(
        self,
        raw_samples: list[dict[str, Any]],
        user_id: UUID,
    ) -> dict[str, list[dict[str, Any]]]:
        return {"heart_rate": [], "steps": [], "spo2": []}

    def get_daily_activity_statistics(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        return []

    def normalize_daily_activity(self, raw_stats: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        raise NotImplementedError("Withings daily activity normalization — Phase C")

    # ------------------------------------------------------------------
    # Orchestrator — called by celery sync_vendor_data_task
    # ------------------------------------------------------------------

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
            results["sleep_sessions_synced"] = self.load_and_save_sleep(
                db, user_id, start_time, end_time,
            )
        except Exception as e:
            log_structured(
                self.logger, "error",
                f"Failed to sync Withings sleep data: {e}",
                provider="withings", task="load_and_save_all", user_id=str(user_id),
            )

        try:
            results["body_measurement_samples_synced"] = self.load_and_save_body_measurement(
                db, user_id, start_time, end_time,
            )
        except Exception as e:
            log_structured(
                self.logger, "error",
                f"Failed to sync Withings body measurements: {e}",
                provider="withings", task="load_and_save_all", user_id=str(user_id),
            )

        return results
