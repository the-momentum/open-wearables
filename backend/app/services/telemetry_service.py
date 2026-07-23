"""Anonymous usage telemetry.

Builds and delivers a daily, anonymous usage ping to the Open Wearables
telemetry collector. The payload contains aggregate counts and configuration
flags only - never user data, tokens, or other PII. See
docs/dev-guides/telemetry.mdx for the full payload reference and opt-out.
"""

import platform
from datetime import datetime, timedelta, timezone
from logging import getLogger
from uuid import uuid4

import httpx
from sqlalchemy import distinct, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import __version__
from app.config import settings
from app.models import (
    DataPointSeries,
    DataSource,
    EventRecord,
    ProviderSetting,
    TelemetryState,
    User,
    UserConnection,
)
from app.schemas.auth import ConnectionStatus

logger = getLogger(__name__)

TELEMETRY_SCHEMA_VERSION = 1
SEND_TIMEOUT_SECONDS = 5.0


class TelemetryService:
    def get_or_create_state(self, db: Session) -> TelemetryState:
        state = db.get(TelemetryState, 1)
        if state is not None:
            return state

        state = TelemetryState(
            id=1,
            instance_id=uuid4(),
            created_at=datetime.now(timezone.utc),
            last_sent_at=None,
        )
        db.add(state)
        try:
            db.commit()
        except IntegrityError:
            # Another worker created the row concurrently - use theirs.
            db.rollback()
            state = db.get(TelemetryState, 1)
            if state is None:  # pragma: no cover - only on DB failure
                raise
        return state

    def build_payload(self, db: Session, event: str) -> dict:
        state = self.get_or_create_state(db)
        now = datetime.now(timezone.utc)
        created_at = state.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        active = UserConnection.status == ConnectionStatus.ACTIVE
        connections_by_provider = {
            provider: count
            for provider, count in db.execute(
                select(UserConnection.provider, func.count()).where(active).group_by(UserConnection.provider)
            )
        }

        return {
            "schema_version": TELEMETRY_SCHEMA_VERSION,
            "instance_id": state.instance_id.hex,
            "event": event,
            "sent_at": now.isoformat(),
            "app_version": __version__,
            "git_sha": settings.GIT_SHA,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "environment": settings.environment.value,
            "instance_age_days": max((now - created_at).days, 0),
            "total_users": db.scalar(select(func.count()).select_from(User)),
            "users_with_active_connection": db.scalar(
                select(func.count(distinct(UserConnection.user_id))).where(active)
            ),
            "active_connections": sum(connections_by_provider.values()),
            "connections_by_provider": connections_by_provider,
            "data_points_by_provider": self._count_by_provider(db, DataPointSeries),
            "workouts_by_provider": self._count_by_provider(db, EventRecord),
            "providers": [
                {
                    "provider": provider_setting.provider,
                    "is_enabled": provider_setting.is_enabled,
                    "live_sync_mode": provider_setting.live_sync_mode,
                    "data_granularity": provider_setting.data_granularity,
                }
                for provider_setting in db.scalars(select(ProviderSetting)).all()
            ],
            "features": {
                "sentry_enabled": settings.SENTRY_ENABLED,
                "ingest_workout_samples": settings.ingest_workout_samples,
                "store_fit_files": settings.store_fit_files,
                "historical_sync_on_connect": settings.historical_sync_on_connect,
                "raw_payload_storage": settings.raw_payload_storage,
                "outgoing_webhooks_enabled": settings.outgoing_webhooks_enabled,
                "default_data_granularity": settings.default_data_granularity,
            },
        }

    def send_ping(self, db: Session, event: str) -> str:
        """Deliver a ping if telemetry is enabled and a ping is due.

        Returns "disabled", "not_due" or "sent". Delivery errors propagate to
        the caller (the Celery task treats them as best-effort failures).
        """
        if not settings.telemetry_enabled:
            return "disabled"

        state = self.get_or_create_state(db)
        if not self._is_due(state, event):
            return "not_due"

        payload = self.build_payload(db, event)
        response = httpx.post(settings.telemetry_endpoint_url, json=payload, timeout=SEND_TIMEOUT_SECONDS)
        response.raise_for_status()

        state.last_sent_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Telemetry ping delivered (event=%s)", event)
        return "sent"

    @staticmethod
    def _is_due(state: TelemetryState, event: str) -> bool:
        if state.last_sent_at is None:
            return True
        last_sent_at = state.last_sent_at
        if last_sent_at.tzinfo is None:
            last_sent_at = last_sent_at.replace(tzinfo=timezone.utc)
        interval_seconds = (
            settings.telemetry_startup_debounce_seconds
            if event == "startup"
            else settings.telemetry_send_interval_seconds
        )
        return datetime.now(timezone.utc) - last_sent_at >= timedelta(seconds=interval_seconds)

    @staticmethod
    def _count_by_provider(db: Session, model: type[DataPointSeries] | type[EventRecord]) -> dict:
        rows = db.execute(
            select(DataSource.provider, func.count())
            .select_from(model)
            .join(DataSource, model.data_source_id == DataSource.id)
            .group_by(DataSource.provider)
        ).all()
        return {provider.value if hasattr(provider, "value") else provider: count for provider, count in rows}


telemetry_service = TelemetryService()
