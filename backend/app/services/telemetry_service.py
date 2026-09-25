"""Anonymous usage telemetry.

Builds and delivers a daily, anonymous usage ping to the Open Wearables
telemetry collector. The payload contains aggregate counts and configuration
flags only - never user data, tokens, or other PII. See
docs/dev-guides/telemetry.mdx for the full payload reference and opt-out.
"""

import platform
from datetime import datetime, timedelta, timezone
from logging import getLogger

import httpx
from sqlalchemy.orm import Session

from app import __version__
from app.config import settings
from app.models import TelemetryState
from app.repositories.telemetry_repository import TelemetryRepository
from app.services.endpoint_usage import endpoint_usage, usage_bucket

logger = getLogger(__name__)

TELEMETRY_SCHEMA_VERSION = 1
SEND_TIMEOUT_SECONDS = 5.0


def count_bucket(count: int | None) -> str:
    """Order-of-magnitude label for a count, so exact numbers never leave the instance.

    Exact counts sent daily would let anyone holding the pings of a small instance
    read day-to-day activity off the differences, or match a total against a public
    profile. "0" stays separate from "1-10" so an empty install is still visible.
    """
    return "0" if not count else usage_bucket(count)


def _bucket_values(counts: dict[str, int]) -> dict[str, str]:
    return {key: count_bucket(count) for key, count in counts.items()}


class TelemetryService:
    def __init__(self) -> None:
        self.repo = TelemetryRepository()

    def get_or_create_state(self, db: Session) -> TelemetryState:
        return self.repo.get_or_create_state(db)

    def build_payload(self, db: Session, event: str) -> dict:
        state = self.get_or_create_state(db)
        now = datetime.now(timezone.utc)
        created_at = state.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        connections_by_provider = self.repo.count_active_connections_by_provider(db)

        return {
            "schema_version": TELEMETRY_SCHEMA_VERSION,
            "instance_id": state.instance_id.hex,
            "event": event,
            "sent_at": now.isoformat(),
            "app_version": __version__,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "environment": settings.environment.value,
            "instance_age_days": max((now - created_at).days, 0),
            "total_users": count_bucket(self.repo.count_users(db)),
            "users_with_active_connection": count_bucket(self.repo.count_users_with_active_connection(db)),
            "active_connections": count_bucket(sum(connections_by_provider.values())),
            "inactive_connections": count_bucket(self.repo.count_inactive_connections(db)),
            "connections_by_provider": _bucket_values(connections_by_provider),
            "data_points_by_provider": _bucket_values(self.repo.count_data_points_by_provider(db)),
            "workouts_by_provider": _bucket_values(self.repo.count_events_by_provider(db, "workout")),
            "sleep_sessions_by_provider": _bucket_values(self.repo.count_events_by_provider(db, "sleep")),
            "providers": [
                {
                    "provider": provider_setting.provider,
                    "is_enabled": provider_setting.is_enabled,
                    "live_sync_mode": provider_setting.live_sync_mode,
                    "data_granularity": provider_setting.data_granularity,
                }
                for provider_setting in self.repo.get_provider_settings(db)
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
            "endpoint_usage": self._endpoint_usage(now),
        }

    def send_ping(self, db: Session, event: str) -> str:
        """Deliver a ping if telemetry is enabled and a ping is due.

        Returns "disabled", "not_due" or "sent". Delivery errors propagate to
        the caller (the Celery task treats them as best-effort failures).
        """
        if not settings.telemetry_enabled:
            return "disabled"

        previous_sent_at = self.repo.get_or_create_state(db).last_sent_at
        claimed_at = self.repo.claim_send(db, self._send_interval(event))
        if claimed_at is None:
            return "not_due"

        try:
            payload = self.build_payload(db, event)
            response = httpx.post(settings.telemetry_endpoint_url, json=payload, timeout=SEND_TIMEOUT_SECONDS)
            response.raise_for_status()
        except Exception:
            # Release the slot so the next hourly run retries.
            self.repo.release_claim(db, claimed_at, previous_sent_at)
            raise

        logger.info("Telemetry ping delivered (event=%s)", event)
        return "sent"

    @staticmethod
    def _send_interval(event: str) -> timedelta:
        """Minimum gap since the last delivery: the startup debounce or the daily interval."""
        seconds = (
            settings.telemetry_startup_debounce_seconds
            if event == "startup"
            else settings.telemetry_send_interval_seconds
        )
        return timedelta(seconds=seconds)

    @staticmethod
    def _endpoint_usage(now: datetime) -> dict | None:
        """Yesterday's bucketed request counters, or None when unavailable.

        Always the last complete UTC day, so a "startup" and a "daily" ping sent on the
        same day carry identical data and the collector can dedupe on the date.
        """
        day = (now - timedelta(days=1)).date()
        try:
            routes = endpoint_usage.read_day(day)
        except Exception:
            logger.debug("Could not read endpoint usage counters", exc_info=True)
            return None
        return {"date": day.isoformat(), "routes": routes}


telemetry_service = TelemetryService()
