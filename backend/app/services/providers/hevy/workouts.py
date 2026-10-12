"""Hevy workouts implementation.

Hevy has no OAuth: every request carries the user's personal API key in the
``api-key`` header (the key is stored on the connection's ``access_token``).
Sync is incremental via GET /v1/workouts/events?since=..., which returns both
'updated' (new or edited, with the full workout) and 'deleted' events — so
edits and deletions made in the Hevy app propagate on the next pull.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import httpx
from pydantic import ValidationError

from app.constants.workout_types.hevy import get_unified_workout_type
from app.database import DbSession
from app.models import DataSource, EventRecord, UserConnection
from app.schemas.auth import ConnectionStatus
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordMetrics,
)
from app.schemas.providers.hevy import HevyWorkout
from app.services.event_record_service import event_record_service
from app.services.providers.base_strategy import IncompleteSyncError
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate
from app.services.raw_payload_storage import store_raw_payload
from app.utils.structured_logging import log_structured

# Hevy caps pageSize at 10 (both /v1/workouts and /v1/workouts/events).
_PAGE_SIZE = 10
# Hard stop for the pagination loop; 1000 pages x 10 = 10k workouts per sync.
_MAX_PAGES = 1000


def _parse_events_page(response: Any) -> tuple[list[dict[str, Any]], int]:
    """The events and page count of one /v1/workouts/events page.

    Raises on any shape it cannot trust (not an object, ``events`` not a list of
    objects, ``page_count`` not a whole number), so a garbled page fails the sync
    like a failed request does instead of reading as "nothing changed".
    """
    if not isinstance(response, dict):
        raise ValueError(f"expected a JSON object, got {type(response).__name__}")
    page_events = response.get("events") or []
    if not isinstance(page_events, list) or not all(isinstance(event, dict) for event in page_events):
        raise ValueError("'events' is not a list of objects")
    raw_count = response.get("page_count") or 1
    if isinstance(raw_count, bool) or not isinstance(raw_count, (int, str)):
        raise ValueError(f"'page_count' is not an integer: {raw_count!r}")
    return page_events, int(raw_count)


def _event_time(event: dict[str, Any]) -> datetime | None:
    """When the event happened: the workout's updated_at, or the deletion time."""
    raw = event.get("deleted_at")
    if event.get("type") == "updated" and isinstance(event.get("workout"), dict):
        raw = event["workout"].get("updated_at")
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _latest_per_workout(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Collapse the feed to the newest event per workout id.

    Hevy lists events newest first, so the first one seen for an id wins; a later
    one only takes over if its own timestamp is strictly newer, which keeps this
    correct even if the feed order ever changes.
    """
    latest: dict[str, tuple[datetime | None, dict[str, Any]]] = {}
    for event in events:
        event_type = event.get("type")
        if event_type == "updated" and isinstance(event.get("workout"), dict):
            workout_id = event["workout"].get("id")
        elif event_type == "deleted":
            workout_id = event.get("id")
        else:
            continue
        if not workout_id:
            continue
        key = str(workout_id)
        when = _event_time(event)
        seen = latest.get(key)
        if seen is None or (when is not None and seen[0] is not None and when > seen[0]):
            latest[key] = (when, event)

    updated: list[dict[str, Any]] = []
    deleted_ids: list[str] = []
    for key, (_, event) in latest.items():
        if event["type"] == "updated":
            updated.append(event["workout"])
        else:
            deleted_ids.append(key)
    return updated, deleted_ids


class HevyWorkouts(BaseWorkoutsTemplate):
    """Hevy implementation of workout syncing (API-key auth, events-feed pull)."""

    def _get_connection(self, db: DbSession, user_id: UUID) -> tuple[UserConnection, str]:
        """The active connection and its API key, or a hard failure.

        The key comes back alongside the connection so the non-null guarantee survives the
        call: ``UserConnection.access_token`` is optional on the model, while for Hevy the
        key *is* the connection, and the 401 path still needs the row to revoke it.
        """
        connection = self.connection_repo.get_by_user_and_provider(db, user_id, self.provider_name)
        if connection is None or connection.status != ConnectionStatus.ACTIVE or not connection.access_token:
            raise ValueError(f"No active Hevy connection with an API key for user {user_id}")
        return connection, connection.access_token

    def _make_api_request(  # type: ignore[override]
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> Any:
        """Request with the user's stored API key; 401 marks the connection revoked.

        Bypasses make_authenticated_request: there is no Bearer token and no
        refresh flow — a rejected key can only be replaced by the user
        submitting a new one.
        """
        connection, api_key = self._get_connection(db, user_id)
        request_headers = {"api-key": api_key, **(headers or {})}
        response = httpx.request(
            method,
            f"{self.api_base_url}{endpoint}",
            params=params,
            headers=request_headers,
            json=json_data,
            timeout=30.0,
        )
        if response.status_code == 401:
            # Key regenerated or Pro subscription lapsed — dead until the user reconnects.
            self.connection_repo.mark_as_revoked(db, connection)
            log_structured(
                self.logger,
                "warning",
                "Hevy API key rejected (401); connection marked revoked",
                provider=self.provider_name,
                task="api_request",
            )
        response.raise_for_status()
        result = response.json()
        store_raw_payload(
            source="api_response",
            provider=self.provider_name,
            payload=result,
            user_id=str(user_id),
            trace_id=endpoint,
        )
        return result

    def get_workout_events(
        self, db: DbSession, user_id: UUID, since: datetime
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Page through /v1/workouts/events and split into (updated workouts, deleted ids).

        All-or-nothing: a failure on any page raises IncompleteSyncError instead of
        returning what earlier pages yielded, so the caller keeps its cursor and the
        next sync asks for the whole window again (replaying it is idempotent).

        Only the newest event per workout id is kept, so an older delete cannot remove
        a newer edit and an older edit cannot overwrite a newer one.
        """
        events: list[dict[str, Any]] = []
        page = 1
        while page <= _MAX_PAGES:
            try:
                response = self._make_api_request(
                    db,
                    user_id,
                    "/v1/workouts/events",
                    params={
                        "since": since.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "page": page,
                        "pageSize": _PAGE_SIZE,
                    },
                )
                page_events, page_count = _parse_events_page(response)
            except Exception as e:
                log_structured(
                    self.logger,
                    "error",
                    f"Error fetching Hevy workout events (page {page}): {e}",
                    provider=self.provider_name,
                    task="get_workout_events",
                )
                raise IncompleteSyncError(f"Hevy events page {page} failed: {e}") from e
            events.extend(page_events)
            if page >= page_count or not page_events:
                break
            page += 1
        return _latest_per_workout(events)

    def get_workouts(self, db: DbSession, user_id: UUID, start_date: datetime, end_date: datetime) -> list[Any]:
        """Workouts updated since ``start_date`` (the events feed has no upper bound)."""
        updated, _ = self.get_workout_events(db, user_id, since=start_date)
        return updated

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        page = max(int(kwargs.get("page", 1)), 1)
        page_size = min(int(kwargs.get("pageSize", kwargs.get("page_size", _PAGE_SIZE))), _PAGE_SIZE)
        return self._make_api_request(db, user_id, "/v1/workouts", params={"page": page, "pageSize": page_size})

    def get_workout_detail_from_api(self, db: DbSession, user_id: UUID, workout_id: str, **kwargs: Any) -> Any:
        return self._make_api_request(db, user_id, f"/v1/workouts/{workout_id}")

    def _normalize_workout(
        self, raw_workout: dict[str, Any], user_id: UUID
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        workout = HevyWorkout.model_validate(raw_workout)
        record_id = uuid4()
        start = workout.start_time
        end = workout.end_time
        duration_seconds = max(int((end - start).total_seconds()), 0)

        metrics: EventRecordMetrics = {}
        total_distance = sum(
            s.distance_meters for ex in workout.exercises for s in ex.sets if s.distance_meters is not None
        )
        if total_distance:
            metrics["distance"] = Decimal(str(total_distance))
        # Full exercise/set structure goes into the segments JSONB so strength
        # data (reps/weights/RPE per set) survives normalization losslessly.
        segments = [ex.model_dump(mode="json", exclude_none=True) for ex in workout.exercises]

        workout_create = EventRecordCreate(
            category="workout",
            type=get_unified_workout_type(workout.title).value,
            source_name="Hevy",
            device_model=None,
            duration_seconds=duration_seconds,
            start_datetime=start,
            end_datetime=end,
            id=record_id,
            external_id=workout.id,
            source=self.provider_name,
            user_id=user_id,
        )
        detail_create = EventRecordDetailCreate(record_id=record_id, segments=segments or None, **metrics)
        return workout_create, detail_create

    def load_data(self, db: DbSession, user_id: UUID, **kwargs: Any) -> int:
        """Pull the events feed since the window start; upsert updates, apply deletes."""
        start = kwargs.get("start") or kwargs.get("start_date")
        if isinstance(start, str):
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        elif isinstance(start, datetime):
            start_dt = start
        else:
            start_dt = datetime.now(timezone.utc) - timedelta(days=30)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)

        updated, deleted_ids = self.get_workout_events(db, user_id, since=start_dt)

        try:
            count = self._apply_events(db, user_id, updated, deleted_ids)
        except Exception as e:
            # A write failed part-way: keep the cursor so the window is replayed.
            db.rollback()
            raise IncompleteSyncError(f"Applying Hevy events failed: {e}") from e
        return count

    def _apply_events(self, db: DbSession, user_id: UUID, updated: list[dict[str, Any]], deleted_ids: list[str]) -> int:
        count = 0
        for raw_workout in updated:
            try:
                record, detail = self._normalize_workout(raw_workout, user_id)
            except ValidationError as e:
                log_structured(
                    self.logger,
                    "error",
                    f"Skipping malformed Hevy workout: {e}",
                    provider=self.provider_name,
                    task="load_data",
                )
                continue
            if self._upsert_workout(db, user_id, record, detail):
                count += 1

        for external_id in deleted_ids:
            deleted = self.workout_repo.delete_by_external_id(db, user_id, external_id, source=self.provider_name)
            if deleted:
                log_structured(
                    self.logger,
                    "info",
                    f"Deleted Hevy workout {external_id} (removed in Hevy)",
                    provider=self.provider_name,
                    task="load_data",
                )
        return count

    def _stored_workouts(self, db: DbSession, user_id: UUID, external_id: str) -> list[EventRecord]:
        """This user's Hevy workouts carrying ``external_id``, oldest first."""
        return (
            db.query(EventRecord)
            .join(DataSource, EventRecord.data_source_id == DataSource.id)
            .filter(
                DataSource.user_id == user_id,
                DataSource.source == self.provider_name,
                EventRecord.category == "workout",
                EventRecord.external_id == external_id,
            )
            .order_by(EventRecord.created_at, EventRecord.id)
            .all()
        )

    def _upsert_workout(
        self, db: DbSession, user_id: UUID, record: EventRecordCreate, detail: EventRecordDetailCreate
    ) -> bool:
        """Insert a new workout, or update the stored one in place, keyed by Hevy's id.

        The record table dedupes on (data_source_id, start, end), so an edit that moves
        a workout's times would otherwise land as a second row. Matching on the Hevy
        id instead keeps one row per workout, and the detail is replaced rather than
        merged so removed exercises or sets do not linger.
        """
        stored = self._stored_workouts(db, user_id, record.external_id) if record.external_id else []
        if not stored:
            created_record = event_record_service.create(db, record)
            event_record_service.create_detail(db, detail.model_copy(update={"record_id": created_record.id}))
            return True

        existing, *duplicates = stored
        if duplicates:
            # Left behind by earlier syncs that inserted an edit as a new row; the
            # detail rows go with them through the foreign key's ON DELETE CASCADE.
            db.query(EventRecord).filter(EventRecord.id.in_([d.id for d in duplicates])).delete(
                synchronize_session=False
            )
            db.flush()

        clash = (
            db.query(EventRecord.id)
            .filter(
                EventRecord.data_source_id == existing.data_source_id,
                EventRecord.category != "meal",
                EventRecord.start_datetime == record.start_datetime,
                EventRecord.end_datetime == record.end_datetime,
                EventRecord.id != existing.id,
            )
            .first()
        )
        if clash is not None:
            db.rollback()
            log_structured(
                self.logger,
                "warning",
                f"Skipping Hevy workout {record.external_id}: its new times collide with another workout",
                provider=self.provider_name,
                task="load_data",
            )
            return False

        existing.type = record.type
        existing.source_name = record.source_name
        existing.duration_seconds = record.duration_seconds
        existing.start_datetime = record.start_datetime
        existing.end_datetime = record.end_datetime
        event_record_service.event_record_detail_repo.delete_by_record_id(db, existing.id, "workout")
        db.commit()
        event_record_service.create_detail(db, detail.model_copy(update={"record_id": existing.id}))
        return True
