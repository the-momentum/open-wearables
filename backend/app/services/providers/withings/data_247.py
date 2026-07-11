"""Withings 24/7 data: body measures (``getmeas``), daily activity (``getactivity``),
and sleep (``getsummary``). Continuous metrics become ``DataPointSeries`` samples;
sleep becomes an ``EventRecord`` + ``EventRecordDetail``, mirroring Oura.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.config import settings
from app.database import DbSession
from app.models import EventRecord
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    TimeSeriesSampleCreate,
)
from app.schemas.providers.withings import (
    WithingsActivity,
    WithingsMeasureGroup,
    WithingsSleepSummary,
)
from app.services.event_record_service import event_record_service
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.withings._client import paginate, scale_measure
from app.services.providers.withings.coverage import ACTIVITY_FIELD_MAP, MEASURE_TYPE_MAP
from app.services.providers.withings.data_requests import ACTIVITY, MEASURES, SLEEP_SUMMARY
from app.services.timeseries_service import timeseries_service
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

# All meastypes requested in one getmeas call.
_REQUESTED_MEASTYPES = ",".join(str(code) for code in MEASURE_TYPE_MAP)

# A few measures arrive in a different unit than the unified SeriesType. After
# decoding (value × 10^unit), multiply by this factor to match OW units.
#   meastype 4 (height): Withings reports metres; OW `height` is centimetres.
_MEASURE_UNIT_FACTOR: dict[int, Decimal] = {
    4: Decimal(100),
}


class Withings247Data(Base247DataTemplate):
    """Withings continuous-data handler."""

    def __init__(self, provider_name: str, api_base_url: str, oauth: BaseOAuthTemplate) -> None:
        super().__init__(provider_name, api_base_url, oauth)
        self.event_record_repo = EventRecordRepository(EventRecord)
        self.connection_repo = UserConnectionRepository()

    # ---------------------- Body measures (getmeas) ----------------------

    def normalize_measures(self, groups: list[dict], user_id: UUID) -> list[TimeSeriesSampleCreate]:
        samples: list[TimeSeriesSampleCreate] = []
        for group in groups:
            # Tolerate a malformed group without dropping the rest of the batch.
            try:
                parsed = WithingsMeasureGroup.model_validate(group)
            except ValidationError as e:
                log_structured(
                    logger,
                    "warning",
                    "Skipping unparseable Withings measure group",
                    provider=self.provider_name,
                    action="measure_group_validation_failed",
                    user_id=str(user_id),
                    error=str(e),
                )
                continue
            samples.extend(self._normalize_measure_group(parsed, user_id))
        return samples

    def _normalize_measure_group(self, group: WithingsMeasureGroup, user_id: UUID) -> list[TimeSeriesSampleCreate]:
        ts = datetime.fromtimestamp(group.date, tz=timezone.utc)
        samples: list[TimeSeriesSampleCreate] = []
        for measure in group.measures:
            series_type = MEASURE_TYPE_MAP.get(measure.type)
            if series_type is None:
                continue  # unmapped type (see MEASURE_TYPE_MAP)
            value = scale_measure(measure)
            factor = _MEASURE_UNIT_FACTOR.get(measure.type)
            if factor is not None:
                value = value * factor
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=ts,
                    value=value,
                    series_type=series_type,
                )
            )
        return samples

    def save_measures(self, db: DbSession, user_id: UUID, start: datetime, end: datetime) -> int:
        groups = paginate(
            db=db,
            user_id=user_id,
            connection_repo=self.connection_repo,
            oauth=self.oauth,
            service_path=MEASURES.service_path,
            action=MEASURES.action,
            params={
                "meastypes": _REQUESTED_MEASTYPES,
                "category": 1,
                "startdate": int(start.timestamp()),
                "enddate": int(end.timestamp()),
            },
            list_key=MEASURES.list_key,
        )
        samples = self.normalize_measures(groups, user_id)
        if samples:
            timeseries_service.bulk_create_samples(db, samples)
            db.commit()
        return len(samples)

    # ---------------------- Daily activity (getactivity) ----------------------

    def normalize_activity(self, rows: list[dict], user_id: UUID) -> list[TimeSeriesSampleCreate]:
        samples: list[TimeSeriesSampleCreate] = []
        for row in rows:
            # Tolerate a malformed row without dropping the rest of the batch.
            try:
                activity = WithingsActivity.model_validate(row)
            except ValidationError as e:
                log_structured(
                    logger,
                    "warning",
                    "Skipping unparseable Withings activity row",
                    provider=self.provider_name,
                    action="activity_row_validation_failed",
                    user_id=str(user_id),
                    error=str(e),
                )
                continue
            # A null deviceid marks a foreign-aggregated day (e.g. via Health Connect);
            # skip it so the origin connector's activity isn't double-counted.
            if activity.deviceid is None:
                logger.debug("Skipping imported Withings activity for %s (no deviceid)", activity.date)
                continue
            try:
                ts = datetime.strptime(activity.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue
            for field, series_type in ACTIVITY_FIELD_MAP.items():
                value = getattr(activity, field)
                if value is None:
                    continue
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=ts,
                        value=Decimal(str(value)),
                        series_type=series_type,
                    )
                )
        return samples

    @staticmethod
    def _ymd_window(start: datetime, end: datetime, widen_ymd_window: bool) -> tuple[str, str]:
        if widen_ymd_window:
            start = start - timedelta(days=1)
            end = end + timedelta(days=1)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    def save_activity(
        self,
        db: DbSession,
        user_id: UUID,
        start: datetime,
        end: datetime,
        *,
        widen_ymd_window: bool = False,
    ) -> int:
        start_ymd, end_ymd = self._ymd_window(start, end, widen_ymd_window)
        rows = paginate(
            db=db,
            user_id=user_id,
            connection_repo=self.connection_repo,
            oauth=self.oauth,
            service_path=ACTIVITY.service_path,
            action=ACTIVITY.action,
            params={
                "startdateymd": start_ymd,
                "enddateymd": end_ymd,
                "data_fields": ",".join(ACTIVITY.data_fields),
            },
            list_key=ACTIVITY.list_key,
        )
        samples = self.normalize_activity(rows, user_id)
        if samples:
            timeseries_service.bulk_create_samples(db, samples)
            db.commit()
        return len(samples)

    # ---------------------- Sleep (getsummary) ----------------------

    def save_sleep(
        self,
        db: DbSession,
        user_id: UUID,
        start: datetime,
        end: datetime,
        *,
        widen_ymd_window: bool = False,
    ) -> int:
        start_ymd, end_ymd = self._ymd_window(start, end, widen_ymd_window)
        rows = paginate(
            db=db,
            user_id=user_id,
            connection_repo=self.connection_repo,
            oauth=self.oauth,
            service_path=SLEEP_SUMMARY.service_path,
            action=SLEEP_SUMMARY.action,
            params={
                "startdateymd": start_ymd,
                "enddateymd": end_ymd,
                "data_fields": ",".join(SLEEP_SUMMARY.data_fields),
            },
            list_key=SLEEP_SUMMARY.list_key,
        )
        count = 0
        for row in rows:
            # Tolerate a malformed night without dropping the rest of the batch.
            try:
                if self._save_sleep_row(db, user_id, row):
                    count += 1
            except Exception as e:
                db.rollback()
                log_and_capture_error(
                    e,
                    logger,
                    "Skipping unparseable Withings sleep row",
                    level="warning",
                    extra={"provider": "withings", "user_id": str(user_id)},
                )
        return count

    def _save_sleep_row(self, db: DbSession, user_id: UUID, row: dict) -> bool:
        summary = WithingsSleepSummary.model_validate(row)
        start_dt = datetime.fromtimestamp(summary.startdate, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(summary.enddate, tz=timezone.utc)
        data = summary.data

        # Stage durations are null for nights imported from an external source.
        deep = data.deepsleepduration or 0
        light = data.lightsleepduration or 0
        rem = data.remsleepduration or 0
        awake = data.wakeupduration or 0
        time_in_bed_seconds = deep + light + rem + awake
        efficiency = data.sleep_efficiency

        record_id = uuid4()
        record = EventRecordCreate(
            id=record_id,
            category="sleep",
            type="sleep_session",
            source_name="Withings",
            duration_seconds=time_in_bed_seconds,
            start_datetime=start_dt,
            end_datetime=end_dt,
            external_id=str(summary.id) if summary.id is not None else None,
            source=self.provider_name,
            user_id=user_id,
        )
        detail = EventRecordDetailCreate(
            record_id=record_id,
            sleep_total_duration_minutes=(deep + light + rem) // 60,
            sleep_time_in_bed_minutes=time_in_bed_seconds // 60,
            # sleep_efficiency is a 0–1 ratio; stored on the 0–100 scale.
            sleep_efficiency_score=Decimal(str(efficiency * 100)) if efficiency is not None else None,
            sleep_deep_minutes=deep // 60,
            sleep_light_minutes=light // 60,
            sleep_rem_minutes=rem // 60,
            sleep_awake_minutes=awake // 60,
            is_nap=False,
        )
        try:
            event_record_service.create_or_merge_sleep(db, user_id, record, detail, settings.sleep_end_gap_minutes)
            return True
        except Exception as e:
            db.rollback()
            log_and_capture_error(
                e,
                logger,
                "Withings sleep save error",
                extra={"provider": "withings", "user_id": str(user_id)},
            )
            return False

    # ---------------------- Combined load ----------------------

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        is_first_sync: bool = False,
    ) -> dict[str, int]:
        """Sync-task entry point. Each domain runs independently so one failure
        doesn't abort the others."""
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        if not start_time:
            start_time = datetime.now(timezone.utc) - timedelta(days=30)
        if not end_time:
            end_time = datetime.now(timezone.utc)

        results: dict[str, int] = {}
        for name, fn in (
            ("measures", self.save_measures),
            ("activity", self.save_activity),
            ("sleep", self.save_sleep),
        ):
            try:
                results[name] = fn(db, user_id, start_time, end_time)
            except Exception as e:
                results[name] = 0
                # Reset the session for the next domain; a failing rollback must
                # not itself abort the remaining domains.
                try:
                    db.rollback()
                except Exception as rollback_error:
                    log_and_capture_error(
                        rollback_error,
                        logger,
                        f"Withings {name} rollback failed",
                        extra={"provider": "withings", "data_type": name, "user_id": str(user_id)},
                    )
                log_and_capture_error(
                    e,
                    logger,
                    f"Withings {name} sync failed",
                    extra={"provider": "withings", "data_type": name, "user_id": str(user_id)},
                )
        return results

    # ---------------------------------------------------------------------
    # Base class stubs — Withings ingests via load_and_save_all, not the
    # generic fetch/normalize hooks. No-ops to satisfy ABC instantiation.
    # ---------------------------------------------------------------------

    def get_sleep_data(
        self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> list[dict[str, Any]]:
        return []

    def normalize_sleep(self, raw_sleep: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        return {}

    def get_recovery_data(
        self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> list[dict[str, Any]]:
        return []

    def normalize_recovery(self, raw_recovery: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        return {}

    def get_activity_samples(
        self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> list[dict[str, Any]]:
        return []

    def normalize_activity_samples(
        self, raw_samples: list[dict[str, Any]], user_id: UUID
    ) -> dict[str, list[dict[str, Any]]]:
        return {}

    def get_daily_activity_statistics(
        self, db: DbSession, user_id: UUID, start_date: datetime, end_date: datetime
    ) -> list[dict[str, Any]]:
        return []

    def normalize_daily_activity(self, raw_stats: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        return {}
