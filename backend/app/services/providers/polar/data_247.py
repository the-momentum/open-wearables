"""Polar AccessLink v3 247-data implementation.

Phase 1 (this file): daily activity summaries — steps, calories, distance,
active/inactive durations — one EventRecord per day under
`category="daily_activity"`, source="polar".

Phase 2 (stubbed): sleep (Sleep Plus Stages), continuous heart rate samples,
nightly recharge. Each returns `[]` / `{}` today; see vault SPEC
`B.TEJO/devops/20260417[SPEC]polar_loop_activity_sleep.md` for Phase 2 scope.

Endpoint reference: https://www.polar.com/accesslink-api/#daily-activity-summary
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import isodate

from app.database import DbSession
from app.models import EventRecord
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
)
from app.schemas.providers.polar import PolarActivityJSON
from app.services.event_record_service import event_record_service
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
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

        Each day is keyed by (source="polar", external_id=<YYYY-MM-DD>). When a
        record already exists for the same day we replace only the detail
        (the record itself is stable since duration/window are derived from
        the Polar response, which is authoritative).
        """
        saved = 0
        for item in normalized:
            if not item:
                continue
            record: EventRecordCreate = item["record"]
            detail: EventRecordDetailCreate = item["detail"]

            existing = self.event_record_repo.get_by_external_id(
                db, source="polar", external_id=item["external_id"], user_id=user_id,
            ) if hasattr(self.event_record_repo, "get_by_external_id") else None

            target_id = existing.id if existing else record.id
            if not existing:
                event_record_service.create(db, record)
            detail_for_record = detail.model_copy(update={"record_id": target_id})
            event_record_service.create_detail(db, detail_for_record, detail_type="workout")
            saved += 1
        return saved

    # -------------------------------------------------------------------------
    # Sleep / Recovery / Activity Samples — Phase 2 stubs
    # -------------------------------------------------------------------------

    def get_sleep_data(self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime) -> list[dict[str, Any]]:
        return []

    def normalize_sleep(self, raw_sleep: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        return {}

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
        """Phase 1: persist daily activity. Sleep/HR/recharge remain 0 until Phase 2."""
        end_dt = end_time or datetime.now(timezone.utc)
        start_dt = start_time or (end_dt - timedelta(days=28 if is_first_sync else 7))

        results: dict[str, int] = {
            "daily_activity_synced": 0,
            "sleep_sessions_synced": 0,   # Phase 2
            "continuous_hr_synced": 0,    # Phase 2
            "nightly_recharge_synced": 0, # Phase 2
        }

        try:
            raw_daily = self.get_daily_activity_statistics(db, user_id, start_dt, end_dt)
            normalized = [self.normalize_daily_activity(item, user_id) for item in raw_daily]
            results["daily_activity_synced"] = self.save_daily_activity_statistics(db, user_id, normalized)
        except Exception as e:
            log_structured(
                self.logger,
                "error",
                f"Polar daily activity sync failed: {e}",
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
