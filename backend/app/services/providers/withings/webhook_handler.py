"""Withings notify-only webhook handler.

Notifications arrive form-encoded without a provider signature; the callback
URL therefore carries the shared token recommended by Withings. The ack must be
fast and 2xx after the token and payload shape are validated. Attribution (does
``userid`` map to a connection) is resolved later, in the worker, so a
disconnected user is acked 200 and ignored rather than 401'd. ``subscribe``
also HEAD-probes the authenticated callback URL, answered by
``handle_challenge``.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from secrets import compare_digest
from typing import Any, assert_never, final
from urllib.parse import parse_qs

from celery import current_app as celery_app
from fastapi import HTTPException, Request, status
from pydantic import ValidationError

from app.config import settings
from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas.auth import LiveSyncMode, resolve_live_sync_mode
from app.schemas.providers.withings import WithingsNotification
from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler
from app.services.providers.withings.applis import APPLI_DOMAIN, PROFILE_CHANGE_APPLI, Domain
from app.services.providers.withings.data_247 import Withings247Data
from app.services.providers.withings.workouts import WithingsWorkouts
from app.services.raw_payload_storage import store_raw_payload
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

_PROCESS_PUSH_TASK = "app.integrations.celery.tasks.webhook_push_task.process_webhook_push"
_MAX_NOTIFY_WINDOW = timedelta(days=31)


@final
@dataclass(frozen=True)
class _ScreenedNotification:
    """A notification that cleared every inbound guard, with its fetch window resolved."""

    notification: WithingsNotification
    domain: Domain
    start: datetime
    end: datetime


class WithingsWebhookHandler(BaseWebhookHandler):
    """Notify-only handler for Withings."""

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
        return bool(expected is not None and actual and compare_digest(actual, expected.get_secret_value()))

    def verify_signature(self, request: Request, body: bytes) -> bool:
        """Verify the callback token and require a userid-bearing notify body."""
        return self._has_valid_callback_token(request) and bool(self.parse_payload(body).get("userid"))

    def handle_challenge(self, request: Request) -> dict[str, Any]:
        """Return 200 for an authenticated subscribe-time HEAD probe."""
        if not self._has_valid_callback_token(request):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Withings callback token")
        return {}

    def supported_event_types(self) -> list[str]:
        return [str(a) for a in APPLI_DOMAIN]

    def _live_sync_mode_allows_webhook(self, db: DbSession) -> bool:
        setting = self.provider_settings_repo.get_all(db).get(self.provider_name)
        configured = setting.live_sync_mode if setting else None
        return resolve_live_sync_mode(configured, self._default_live_sync_mode) == LiveSyncMode.WEBHOOK

    @staticmethod
    def _bounded_window(notification: WithingsNotification) -> tuple[datetime, datetime, str | None] | None:
        window = notification.resolve_window()
        if window is None:
            return None
        start, end = window
        if end < start:
            return start, end, "invalid_date_range"
        if end - start > _MAX_NOTIFY_WINDOW:
            return start, end, "date_range_too_large"
        return start, end, None

    def _screen(self, db: DbSession, payload: dict[str, Any]) -> _ScreenedNotification | dict[str, Any]:
        """Run the shared inbound gauntlet: validate → appli → window → live-sync mode.

        Returns the resolved notification and fetch window, or an ``ignored``
        result to be returned verbatim. Shared by ``dispatch`` and
        ``process_payload`` so they stay in lock-step; the worker re-runs it
        because the payload is untrusted and the mode may have flipped to PULL
        while the notification sat in the queue. User attribution is left to the
        caller — the two differ only in how they report an unknown user.
        """
        try:
            notification = WithingsNotification.model_validate(payload)
        except ValidationError:
            return {"status": "ignored", "reason": "invalid_payload_fields"}

        if notification.appli == PROFILE_CHANGE_APPLI:
            return {"status": "ignored", "reason": "profile_change", "action": notification.action}

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

        return _ScreenedNotification(notification=notification, domain=domain, start=start, end=end)

    def dispatch(self, db: DbSession, payload: dict[str, Any]) -> dict[str, Any]:
        """Acknowledge fast, then enqueue the data fetch on the ``webhook_sync`` queue."""
        screened = self._screen(db, payload)
        if isinstance(screened, dict):
            return screened

        userid = screened.notification.userid
        if not self.connection_repo.get_by_provider_user_id(db, "withings", userid):
            return {"status": "ignored", "reason": "user_not_found", "withings_user_id": userid}

        celery_app.send_task(
            _PROCESS_PUSH_TASK,
            args=["withings", payload, str(userid)],
            queue="webhook_sync",
        )
        return {"status": "accepted", "appli": screened.notification.appli}

    # ---------------------- async processing (Celery worker) ----------------------

    def process_payload(self, db: DbSession, payload: Any, trace_id: str) -> dict[str, Any]:
        """Fetch and persist the data referenced by a notification.

        Runs in the ``process_webhook_push`` worker with its own session. Raw
        capture happens here, off the inbound ack budget. The payload is
        untrusted, so the guards are re-run via ``_screen`` and the user
        re-resolved from ``userid``.
        """
        store_raw_payload(source="webhook", provider="withings", payload=payload, trace_id=str(payload.get("userid")))

        screened = self._screen(db, payload)
        if isinstance(screened, dict):
            return screened

        connection = self.connection_repo.get_by_provider_user_id(db, "withings", screened.notification.userid)
        if not connection:
            return {"status": "user_not_found", "withings_user_id": screened.notification.userid}

        user_id = connection.user_id
        domain, start, end = screened.domain, screened.start, screened.end
        if domain == "measures":
            # appli 1/2/4/58 all fetch via getmeas (requested meastypes in coverage.py).
            saved = self.data_247.save_measures(db, user_id, start, end)
        elif domain == "sleep":
            saved = self.data_247.save_sleep(db, user_id, start, end, widen_ymd_window=True)
        elif domain == "activity_workouts":
            # appli 16 covers both daily activity and workouts.
            saved = self.data_247.save_activity(db, user_id, start, end, widen_ymd_window=True)
            saved += self.workouts.load_data(
                db,
                user_id,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                widen_ymd_window=True,
            )
        else:
            assert_never(domain)

        log_structured(
            logger,
            "info",
            "Withings webhook processed",
            provider="withings",
            appli=screened.notification.appli,
            domain=domain,
            user_id=str(user_id),
            records=saved,
            trace_id=trace_id,
        )
        return {"status": "processed", "domain": domain, "records_saved": saved, "user_id": str(user_id)}
