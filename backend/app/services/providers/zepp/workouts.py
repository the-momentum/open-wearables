from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.constants.workout_types.zepp import get_unified_workout_type
from app.database import DbSession
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.auth import ConnectionStatus
from app.schemas.enums import ProviderName
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
)
from app.services.event_record_service import event_record_service
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate
from app.services.providers.zepp.client import DEFAULT_HOST, ZeppAuthExpiredError, ZeppClient
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)


class ZeppWorkouts(BaseWorkoutsTemplate):
    """Zepp / Huami implementation of workouts template."""

    def __init__(
        self,
        workout_repo: EventRecordRepository,
        connection_repo: UserConnectionRepository,
        provider_name: str = ProviderName.ZEPP.value,
        api_base_url: str = "",
        oauth: Any = None,
    ) -> None:
        super().__init__(workout_repo, connection_repo, provider_name, api_base_url, oauth)
        self.logger = logger

    def _get_client(self, db: DbSession, user_id: UUID) -> tuple[ZeppClient | None, Any | None]:
        """Resolve active user connection and initialize ZeppClient."""
        conn = self.connection_repo.get_active_connection(db, user_id, self.provider_name)
        if not conn or not conn.access_token or not conn.provider_user_id:
            return None, conn

        client = ZeppClient(
            apptoken=conn.access_token,
            user_id=conn.provider_user_id,
            host=conn.refresh_token or DEFAULT_HOST,
        )
        return client, conn

    def _handle_auth_expired(self, db: DbSession, conn: Any) -> None:
        """Mark connection as expired when token validation fails."""
        if conn:
            conn.status = ConnectionStatus.EXPIRED
            conn.updated_at = datetime.now(timezone.utc)
            db.add(conn)
            db.commit()
            log_structured(
                self.logger,
                "warning",
                "Zepp credentials expired or unauthorized; connection marked as EXPIRED",
                user_id=str(conn.user_id),
                provider=self.provider_name,
            )

    def _normalize_workout(
        self,
        raw_workout: dict[str, Any],
        user_id: UUID,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        """Convert Huami workout dictionary into EventRecordCreate and EventRecordDetailCreate."""
        track_id = str(raw_workout.get("trackid") or raw_workout.get("trackId") or "").strip()
        try:
            ts = int(float(track_id))
        except (ValueError, TypeError):
            ts = 0

        start_dt = datetime.fromtimestamp(ts, tz=timezone.utc) if ts > 0 else datetime.now(timezone.utc)
        duration_sec = int(float(raw_workout.get("run_time") or 0))
        end_dt = start_dt + timedelta(seconds=duration_sec) if duration_sec > 0 else start_dt

        activity_type_id = int(float(raw_workout.get("type") or 0))
        unified_type = get_unified_workout_type(activity_type_id)

        source_str = str(raw_workout.get("source") or "")
        device_model = source_str.replace(".huami.com", "").replace("run.", "").strip() or None

        record_id = uuid4()
        record = EventRecordCreate(
            id=record_id,
            user_id=user_id,
            provider=ProviderName.ZEPP,
            category="workout",
            type=unified_type.value,
            source_name=device_model or "zepp",
            device_model=device_model,
            duration_seconds=duration_sec if duration_sec > 0 else None,
            start_datetime=start_dt,
            end_datetime=end_dt,
            source="zepp",
            external_id=track_id or None,
        )

        distance_m = float(raw_workout.get("dis") or 0)
        energy_kcal = float(raw_workout.get("calorie") or 0)
        raw_avg_hr = raw_workout.get("avg_heart_rate")
        avg_hr = round(float(raw_avg_hr)) if raw_avg_hr is not None else None

        raw_max_hr = raw_workout.get("max_heart_rate")
        max_hr = int(float(raw_max_hr)) if raw_max_hr is not None else None

        raw_steps = raw_workout.get("total_step")
        steps = int(float(raw_steps)) if raw_steps is not None else None

        detail = EventRecordDetailCreate(
            record_id=record_id,
            moving_time_seconds=duration_sec if duration_sec > 0 else None,
            distance=Decimal(str(distance_m)) if distance_m > 0 else None,
            energy_burned=Decimal(str(energy_kcal)) if energy_kcal > 0 else None,
            heart_rate_avg=Decimal(str(avg_hr)) if avg_hr is not None else None,
            heart_rate_max=max_hr,
            steps_count=steps,
        )

        return record, detail

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch workouts from Zepp API for date range."""
        client, conn = self._get_client(db, user_id)
        if not client:
            return []

        start_track_id = int(start_date.timestamp())
        stop_track_id = int(end_date.timestamp())

        try:
            with client:
                res = client.get_workouts(start_track_id=start_track_id, stop_track_id=stop_track_id)
                data = res.get("data") if isinstance(res, dict) else None
                summaries = data.get("summary") if isinstance(data, dict) else None
                return summaries if isinstance(summaries, list) else []
        except ZeppAuthExpiredError:
            self._handle_auth_expired(db, conn)
            raise
        except Exception as exc:
            log_structured(
                self.logger,
                "error",
                f"Failed to fetch workouts from Zepp API: {exc}",
                user_id=str(user_id),
                provider=self.provider_name,
            )
            return []

    def load_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime | str | None = None,
        end_date: datetime | str | None = None,
        **kwargs: Any,
    ) -> int:
        """Load and persist workouts from Zepp API.

        Returns:
            int: Number of workouts processed and saved.
        """
        client, conn = self._get_client(db, user_id)
        if not client:
            return 0

        # Resolve date boundaries
        if isinstance(start_date, str):
            try:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                start_dt = None
        else:
            start_dt = start_date

        if isinstance(end_date, str):
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                end_dt = None
        else:
            end_dt = end_date

        start_track_id = int(start_dt.timestamp()) if start_dt else 0
        stop_track_id = int(end_dt.timestamp()) if end_dt else int(datetime.now(timezone.utc).timestamp())

        try:
            with client:
                res = client.get_workouts(start_track_id=start_track_id, stop_track_id=stop_track_id)
        except ZeppAuthExpiredError:
            self._handle_auth_expired(db, conn)
            raise
        except Exception as exc:
            log_structured(
                self.logger,
                "error",
                f"Failed to load Zepp workouts: {exc}",
                user_id=str(user_id),
                provider=self.provider_name,
            )
            return 0

        data = res.get("data") if isinstance(res, dict) else None
        summaries = data.get("summary") if isinstance(data, dict) else None
        if not isinstance(summaries, list):
            return 0

        count = 0
        for item in summaries:
            if not isinstance(item, dict):
                continue

            track_id = str(item.get("trackid") or item.get("trackId") or "").strip()
            try:
                ts = int(float(track_id))
            except (ValueError, TypeError):
                continue
            if ts <= 0:
                continue

            try:
                record, detail = self._normalize_workout(item, user_id)
                created_record = event_record_service.create(db, record)
                detail_for_record = detail.model_copy(update={"record_id": created_record.id})
                event_record_service.create_detail(db, detail_for_record)
                count += 1
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to process Zepp workout {track_id}: {e}",
                    user_id=str(user_id),
                    provider=self.provider_name,
                )

        return count
