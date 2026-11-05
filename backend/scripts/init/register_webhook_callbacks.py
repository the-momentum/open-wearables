#!/usr/bin/env python3
"""Queue re-registration of webhooks whose callback URL carries a token derived from SECRET_KEY.

A new SECRET_KEY or API_BASE_URL changes that URL, and the provider keeps calling the old one until
the subscription is replaced. The reconcile task replaces it then and skips it otherwise.
"""

from app.database import DbSession, SessionLocal
from app.integrations.celery.core import create_celery
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas.auth import LiveSyncMode
from app.services.providers.factory import ProviderFactory


def register_webhook_callbacks(db: DbSession) -> list[str]:
    factory = ProviderFactory()
    queued = []
    for provider, provider_settings in ProviderSettingsRepository().get_all(db).items():
        if provider_settings.live_sync_mode != LiveSyncMode.WEBHOOK:
            continue
        strategy = factory.get_provider(provider)
        if strategy.webhooks is not None and strategy.webhooks.requires_callback_token:
            strategy.apply_live_sync_mode(LiveSyncMode.WEBHOOK)
            queued.append(provider)
    return queued


if __name__ == "__main__":
    # Outside the app, the Celery app is not configured yet: without this send_task goes to the default broker.
    create_celery()
    with SessionLocal() as db:
        print(f"webhook callback registration queued for: {register_webhook_callbacks(db) or 'none'}")
