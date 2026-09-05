"""Withings workouts (``getworkouts``) → unified EventRecord + EventRecordDetail."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.config import settings
from app.constants.withings_requests import WORKOUTS
from app.constants.workout_types.withings import OFFICIAL_WITHINGS_CATEGORY_IDS, get_unified_workout_type
from app.database import DbSession
from app.schemas.model_crud.activities import EventRecordCreate, EventRecordDetailCreate
from app.schemas.providers.withings import WithingsWorkout
from app.services.event_record_service import event_record_service
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate
from app.services.providers.withings.rpc_client import paginate
from app.services.providers.withings.timezone import zone_offset_at
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

# getworkouts requires both bounds; used only when PULL_SYNC_LOOKBACK is unset.
_FALLBACK_LOOKBACK = timedelta(days=30)


class WithingsWorkouts(BaseWorkoutsTemplate):
    def get_workouts(self, db: DbSession, user_id: UUID, start_date: datetime, end_date: datetime) -> list[Any]:
        return self.get_workouts_from_api(
            db,
            user_id,
            startdateymd=start_date.strftime("%Y-%m-%d"),
            enddateymd=end_date.strftime("%Y-%m-%d"),
        )

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> list[dict]:
        # Accept Withings-native ymd keys or the generic ISO keys the sync task emits.
        start_ymd = kwargs.get("startdateymd") or self._to_ymd(kwargs.get("start_date"))
        end_ymd = kwargs.get("enddateymd") or self._to_ymd(kwargs.get("end_date"))
        # Missing or invalid bounds fall back to the configured trailing pull window.
        now = datetime.now(timezone.utc)
        if start_ymd is None:
            start_ymd = (now - (settings.pull_sync_lookback or _FALLBACK_LOOKBACK)).strftime("%Y-%m-%d")
        if end_ymd is None:
            end_ymd = now.strftime("%Y-%m-%d")
        # getworkouts keys on the user's local day while every caller's window is
        # UTC, so both edges can clip a day for anyone outside UTC. Widen always;
        # the extra local day per edge is deduplicated by the upsert.
        start_ymd = self._shift_ymd(start_ymd, -1)
        end_ymd = self._shift_ymd(end_ymd, +1)
        return paginate(
            db=db,
            user_id=user_id,
            connection_repo=self.connection_repo,
            oauth=self.oauth,
            service_path=WORKOUTS.service_path,
            action=WORKOUTS.action,
            params={
                "startdateymd": start_ymd,
                "enddateymd": end_ymd,
                "data_fields": ",".join(WORKOUTS.data_fields),
            },
            list_key=WORKOUTS.list_key,
        ).rows

    @staticmethod
    def _to_ymd(value: Any) -> str | None:
        """Convert an ISO datetime string or ``datetime`` to ``YYYY-MM-DD``.

        Returns ``None`` for falsy inputs (no bound was requested) and for values that
        cannot be parsed. The latter is logged: the caller then substitutes its default
        window, so the fetch silently covers a different range than the one asked for.
        """
        if not value:
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            log_structured(
                logger,
                "warning",
                "Unparseable Withings workout date; falling back to the default window",
                provider="withings",
                action="workout_date_parse_failed",
                value=str(value),
            )
            return None

    @staticmethod
    def _shift_ymd(ymd: str, days: int) -> str:
        return (datetime.strptime(ymd, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")

    def _normalize_workout(
        self,
        raw_workout: WithingsWorkout,
        user_id: UUID,
        user_connection_id: UUID | None = None,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        start_dt = datetime.fromtimestamp(raw_workout.startdate, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(raw_workout.enddate, tz=timezone.utc)
        # Workout summaries are keyed by the local end date, matching sleep summaries.
        zone_offset = zone_offset_at(
            raw_workout.timezone,
            end_dt,
            logger,
            action="workout_timezone_invalid",
            user_id=str(user_id),
            workout_id=raw_workout.id,
        )
        workout_type = get_unified_workout_type(raw_workout.category)
        data = raw_workout.data
        record_id = uuid4()
        duration_seconds = int(end_dt.timestamp() - start_dt.timestamp())
        if duration_seconds < 0:
            raise ValueError("enddate must be after startdate")

        record = EventRecordCreate(
            id=record_id,
            category="workout",
            type=workout_type.value,
            source_name="Withings",
            duration_seconds=duration_seconds,
            start_datetime=start_dt,
            end_datetime=end_dt,
            zone_offset=zone_offset,
            external_id=str(raw_workout.id) if raw_workout.id is not None else None,
            source=self.provider_name,
            provider=self.provider_name,
            user_connection_id=user_connection_id,
            user_id=user_id,
        )
        detail = EventRecordDetailCreate(
            record_id=record_id,
            heart_rate_avg=Decimal(str(data.hr_average)) if data.hr_average is not None else None,
            heart_rate_min=data.hr_min,
            heart_rate_max=data.hr_max,
            steps_count=data.steps,
            energy_burned=Decimal(str(data.calories)) if data.calories is not None else None,
            distance=Decimal(str(data.distance)) if data.distance is not None else None,
        )
        return record, detail

    def load_data(self, db: DbSession, user_id: UUID, **kwargs: Any) -> int:
        connection = self.connection_repo.get_active_connection(db, user_id, self.provider_name)
        user_connection_id = connection.id if connection is not None and isinstance(connection.id, UUID) else None
        raw_workouts = self.get_workouts_from_api(db, user_id, **kwargs)
        processed = 0
        skipped = 0
        failed = 0
        warned_unknown_categories: set[int] = set()
        for raw in raw_workouts:
            # Tolerate a malformed record without dropping the rest of the batch.
            try:
                workout = WithingsWorkout.model_validate(raw)
            except ValidationError as e:
                log_structured(
                    logger,
                    "warning",
                    "Skipping unparseable Withings workout",
                    provider=self.provider_name,
                    action="workout_validation_failed",
                    user_id=str(user_id),
                    error=str(e),
                )
                skipped += 1
                continue
            if workout.category == 128:
                skipped += 1
                continue
            if (
                workout.category not in OFFICIAL_WITHINGS_CATEGORY_IDS
                and workout.category not in warned_unknown_categories
            ):
                log_structured(
                    logger,
                    "warning",
                    "Unknown Withings workout category; using OTHER",
                    provider=self.provider_name,
                    action="workout_category_unknown",
                    user_id=str(user_id),
                    category_id=workout.category,
                )
                warned_unknown_categories.add(workout.category)
            try:
                record, detail = self._normalize_workout(workout, user_id, user_connection_id)
            except ValueError as e:
                log_structured(
                    logger,
                    "warning",
                    "Skipping invalid Withings workout",
                    provider=self.provider_name,
                    action="workout_normalization_failed",
                    user_id=str(user_id),
                    workout_id=workout.id,
                    error=str(e),
                )
                skipped += 1
                continue
            try:
                # create() dedups on the (source, start, end) window and returns the
                # canonical record; the detail FK must point at its id, not ours.
                created = event_record_service.create(db, record)
                event_record_service.create_detail(db, detail.model_copy(update={"record_id": created.id}))
                processed += 1
            except Exception as e:
                # Reset the session so one bad record doesn't poison the batch.
                db.rollback()
                log_and_capture_error(
                    e,
                    logger,
                    "Failed to save Withings workout",
                    extra={
                        "provider": self.provider_name,
                        "action": "workout_save_failed",
                        "user_id": str(user_id),
                        "workout_id": workout.id,
                    },
                )
                failed += 1
                continue
        if skipped or failed:
            log_structured(
                logger,
                "info",
                "Withings workouts sync completed with dropped records",
                provider=self.provider_name,
                action="workouts_sync_summary",
                user_id=str(user_id),
                processed=processed,
                skipped=skipped,
                failed=failed,
            )
        return processed
