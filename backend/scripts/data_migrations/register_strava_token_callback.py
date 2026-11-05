#!/usr/bin/env python3
"""Move the Strava webhook subscription to the callback URL that carries the callback token.

Strava keeps calling the URL it was subscribed with, and the token-less one is now rejected. While
Strava is in webhook mode, this queues the reconcile task, which replaces the subscription once the
API is up. Runs once per instance (data_migration); after a new SECRET_KEY or API_BASE_URL, call
POST /api/v1/providers/strava/webhooks/subscriptions instead.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/register_strava_token_callback.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/register_strava_token_callback.py
"""

import argparse

from sqlalchemy.orm import Session

from app.database import engine
from app.integrations.celery.core import create_celery
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas.auth import LiveSyncMode
from app.services.data_migration_service import data_migration_service
from app.services.providers.factory import ProviderFactory


def register_strava_token_callback(db: Session, *, dry_run: bool = False) -> bool:
    if ProviderSettingsRepository().get_live_sync_mode(db, "strava") != LiveSyncMode.WEBHOOK:
        print("Strava is not in webhook mode, nothing to register.")
        return not dry_run
    if dry_run:
        print("Strava is in webhook mode, its registration would be queued.")
        return False
    ProviderFactory().get_provider("strava").apply_live_sync_mode(LiveSyncMode.WEBHOOK)
    print("Strava webhook registration queued.")
    return True


def main(dry_run: bool) -> None:
    # Outside the app, the Celery app is not configured yet: without this send_task goes to the default broker.
    create_celery()
    with engine.connect() as connection, Session(bind=connection) as db:
        data_migration_service.run(
            db,
            "register_strava_token_callback",
            lambda: register_strava_token_callback(db, dry_run=dry_run),
            dry_run=dry_run,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report what would be queued without queueing it")
    main(dry_run=parser.parse_args().dry_run)
