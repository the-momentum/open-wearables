#!/usr/bin/env python3
"""Move the Strava webhook subscription to the callback URL that carries the callback token.

Strava keeps calling the URL it was subscribed with, and the token-less one is now rejected. While
Strava is in webhook mode, this queues the reconcile task, which replaces the subscription once the
API is up. Runs once per instance (data_migration); after a new SECRET_KEY or API_BASE_URL, call
POST /api/v1/providers/strava/webhooks/subscriptions instead.
"""

from sqlalchemy.orm import Session

from app.database import engine
from app.integrations.celery.core import create_celery
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas.auth import LiveSyncMode
from app.services.data_migration_service import data_migration_service
from app.services.providers.factory import ProviderFactory


def register_strava_token_callback(db: Session) -> bool:
    if ProviderSettingsRepository().get_live_sync_mode(db, "strava") != LiveSyncMode.WEBHOOK:
        print("Strava is not in webhook mode, nothing to register.")
        return True
    ProviderFactory().get_provider("strava").apply_live_sync_mode(LiveSyncMode.WEBHOOK)
    print("Strava webhook registration queued.")
    return True


def main() -> None:
    # Outside the app, the Celery app is not configured yet: without this send_task goes to the default broker.
    create_celery()
    with engine.connect() as connection, Session(bind=connection) as db:
        data_migration_service.run(db, "register_strava_token_callback", lambda: register_strava_token_callback(db))


if __name__ == "__main__":
    main()
