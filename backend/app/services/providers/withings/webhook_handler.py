"""Authenticate Withings notifications, acknowledge them, and defer ingestion to Celery."""

import logging
from datetime import datetime, timedelta
from secrets import compare_digest
from typing import Any, assert_never
from urllib.parse import parse_qs
from uuid import UUID, uuid4

from celery import current_app as celery_app
from fastapi import HTTPException, Request, status
from pydantic import ValidationError

from app.config import settings
from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas.auth import LiveSyncMode
from app.schemas.providers.withings import WithingsNotification
from app.schemas.sync_status import SyncStatus
from app.services import sync_status_service
from app.services.outgoing_webhooks.events import on_connection_revoked
from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler
from app.services.providers.withings.applis import APPLI_DOMAIN, SUBSCRIBED_APPLIS, Domain
from app.services.providers.withings.data_247 import Withings247Data
from app.services.providers.withings.workouts import WithingsWorkouts
from app.services.raw_payload_storage import store_raw_payload
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

_PROCESS_PUSH_TASK = "app.integrations.celery.tasks.webhook_push_task.process_webhook_push"
_MAX_NOTIFY_WINDOW = timedelta(days=31)


class WithingsWebhookHandler(BaseWebhookHandler):
    user_id_field = "userid"

    def __init__(
        self,
        data_247: Withings247Data,
        workouts: WithingsWorkouts,
        default_live_sync_mode: LiveSyncMode | None = LiveSyncMode.PULL,
    ) -> None:
        super().__init__("withings")
        self.data_247 = data_247
        self.workouts = workouts  # appli 16 covers both daily activity and workouts
        self.connection_repo = UserConnectionRepository()
        self.provider_settings_repo = ProviderSettingsRepository()
        # Provider's default when no admin override is stored (Withings: PULL).
        self._default_live_sync_mode = default_live_sync_mode

    # ---------------------- inbound request handling ----------------------

    def parse_payload(self, body: bytes) -> dict[str, Any]:
        parsed = parse_qs(body.decode("utf-8"))
        return {k: v[0] for k, v in parsed.items()}

    @staticmethod
    def _has_valid_callback_token(request: Request) -> bool:
        expected = settings.withings_webhook_token
        actual = request.query_params.get("token")
        if expected is None or not actual:
            return False
        # compare_digest raises TypeError on non-ASCII str; the token is caller-supplied.
        return compare_digest(actual.encode("utf-8"), expected.get_secret_value().encode("utf-8"))

    def verify_signature(self, request: Request, body: bytes) -> bool:
        """Verify the callback token and require a userid-bearing notify body."""
        return self._has_valid_callback_token(request) and bool(self.parse_payload(body).get("userid"))

    def handle_probe(self, request: Request) -> None:
        """Accept an authenticated subscribe-time HEAD probe."""
        if not self._has_valid_callback_token(request):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Withings callback token")

    def supported_event_types(self) -> list[str]:
        return [str(appli) for appli in SUBSCRIBED_APPLIS]

    def _live_sync_mode_allows_webhook(self, db: DbSession) -> bool:
        configured = self.provider_settings_repo.get_live_sync_mode(db, self.provider_name)
        return (configured or self._default_live_sync_mode) == LiveSyncMode.WEBHOOK

    @staticmethod
    def _bounded_window(notification: WithingsNotification) -> tuple[datetime, datetime, str | None] | None:
        window = notification.resolve_notify_window()
        if window is None:
            return None
        start, end = window
        if end < start:
            return start, end, "invalid_date_range"
        if end - start > _MAX_NOTIFY_WINDOW:
            return start, end, "date_range_too_large"
        return start, end, None

    def _screen(self, payload: dict[str, Any]) -> WithingsNotification | dict[str, Any]:
        """Validate an inbound notification; a dict is the reason to ignore it."""
        try:
            notification = WithingsNotification.model_validate(payload)
        except ValidationError:
            return {"status": "ignored", "reason": "invalid_payload_fields"}

        if notification.is_profile_change and not notification.revokes_access:
            return {"status": "ignored", "reason": "profile_change", "action": notification.action}
        return notification

    def _fetch_plan(
        self, db: DbSession, notification: WithingsNotification
    ) -> tuple[Domain, datetime, datetime] | dict[str, Any]:
        """Resolve which domain and window a data notification asks us to fetch."""
        domain = APPLI_DOMAIN.get(notification.appli)
        if domain is None:
            return {"status": "ignored", "reason": f"unhandled_appli: {notification.appli}"}

        bounded = self._bounded_window(notification)
        if bounded is None:
            return {"status": "ignored", "reason": "missing_date_range"}
        start, end, invalid_reason = bounded
        if invalid_reason:
            return {"status": "ignored", "reason": invalid_reason}

        if not self._live_sync_mode_allows_webhook(db):
            return {"status": "ignored", "reason": "live_sync_mode_not_webhook"}
        return domain, start, end

    def dispatch(self, db: DbSession, payload: dict[str, Any]) -> dict[str, Any]:
        """Store the raw payload, then acknowledge fast and enqueue the data fetch
        (or revoke) on the ``webhook_sync`` queue."""
        trace_id = str(uuid4())[:8]
        store_raw_payload(source="webhook", provider="withings", payload=payload, trace_id=trace_id)

        notification = self._screen(payload)
        if isinstance(notification, dict):
            return notification

        userid = notification.userid
        if notification.is_profile_change:
            # One Withings account can back several local profiles; all revoke together.
            known = bool(self.connection_repo.get_all_by_provider_user_id(db, "withings", userid))
        else:
            plan = self._fetch_plan(db, notification)
            if isinstance(plan, dict):
                return plan
            known = self.connection_repo.get_by_provider_user_id(db, "withings", userid) is not None
        if not known:
            return {"status": "ignored", "reason": "user_not_found", "withings_user_id": userid}

        celery_app.send_task(
            _PROCESS_PUSH_TASK,
            args=["withings", payload, trace_id],
            queue="webhook_sync",
        )
        return {"status": "accepted", "appli": notification.appli}

    # ---------------------- async processing (Celery worker) ----------------------

    def process_payload(self, db: DbSession, payload: Any, trace_id: str) -> dict[str, Any]:
        """Fetch and persist the data referenced by a notification.

        Runs in the ``process_webhook_push`` worker with its own session. The
        payload is untrusted, so the guards are re-run via ``_screen`` and the
        user re-resolved from ``userid``. Withings notifies once per category, so
        one user action arrives as a small burst over the same window; the writes
        are idempotent upserts, so a repeat costs a refetch and nothing more.
        """
        notification = self._screen(payload)
        if isinstance(notification, dict):
            return notification

        if notification.is_profile_change:
            return self._revoke_local_connections(db, notification, trace_id)

        plan = self._fetch_plan(db, notification)
        if isinstance(plan, dict):
            return plan
        domain, start, end = plan

        connections = self.connection_repo.get_all_by_provider_user_id(db, "withings", notification.userid)
        if not connections:
            return {"status": "user_not_found", "withings_user_id": notification.userid}

        saved = 0
        user_ids: list[str] = []
        per_user: list[tuple[UUID, int]] = []
        for connection in connections:
            user_id = connection.user_id
            items = self._fetch_domain(db, user_id, domain, start, end)
            saved += items
            user_ids.append(str(user_id))
            per_user.append((user_id, items))

        # Emit only after the complete fan-out succeeds. A retry must not leave
        # terminal events for users processed before a later top-level failure.
        for user_id, items in per_user:
            sync_status_service.webhook_delivered(
                str(user_id),
                "withings",
                status=SyncStatus.SUCCESS if items else SyncStatus.SKIPPED,
                items_processed=items,
                message=f"Withings webhook processed {items} items",
                metadata={"domain": domain},
            )

        log_structured(
            logger,
            "info",
            "Withings webhook processed",
            provider="withings",
            appli=notification.appli,
            domain=domain,
            user_ids=user_ids,
            items_processed=saved,
            trace_id=trace_id,
        )
        return {
            "status": "processed",
            "domain": domain,
            "records_saved": saved,
            "items_processed": saved,
            "user_ids": user_ids,
        }

    def _fetch_domain(self, db: DbSession, user_id: UUID, domain: Domain, start: datetime, end: datetime) -> int:
        """Fetch and persist the data one notification domain points at."""
        if domain == "measures":
            # appli 1/2/4/58 all fetch via getmeas (requested meastypes in coverage.py).
            return self.data_247.save_measures(db, user_id, start, end)
        if domain == "sleep":
            return self.data_247.save_sleep(db, user_id, start, end)
        if domain == "activity_workouts":
            # appli 16 covers both daily activity and workouts.
            return self.data_247.save_activity(db, user_id, start, end) + self.workouts.load_data(
                db, user_id, start_date=start.isoformat(), end_date=end.isoformat()
            )
        assert_never(domain)

    def _revoke_local_connections(
        self, db: DbSession, notification: WithingsNotification, trace_id: str
    ) -> dict[str, Any]:
        """Revoke every local connection for this Withings account — access was lost upstream.

        One Withings account can be linked to multiple OW users (multi-account
        fan-out); all of them lose access together, so all of them are revoked.
        """
        connections = self.connection_repo.get_all_by_provider_user_id(db, "withings", notification.userid)
        if not connections:
            return {"status": "user_not_found", "withings_user_id": notification.userid}

        user_ids = [str(connection.user_id) for connection in connections]
        for connection in connections:
            if self.connection_repo.disconnect(db, connection.user_id, "withings"):
                db.refresh(connection)
                on_connection_revoked(
                    user_id=connection.user_id,
                    provider="withings",
                    connection_id=connection.id,
                    reason=f"provider_{notification.action}",
                    revoked_at=connection.updated_at.isoformat(),
                )

        log_structured(
            logger,
            "info",
            "Withings profile change revoked local connections",
            provider="withings",
            action=notification.action,
            withings_user_id=notification.userid,
            user_ids=user_ids,
            trace_id=trace_id,
        )
        return {
            "status": "revoked",
            "action": notification.action,
            "withings_user_id": notification.userid,
            "user_ids": user_ids,
        }
