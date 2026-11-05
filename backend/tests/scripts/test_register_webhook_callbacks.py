from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.constants.celery_tasks import CeleryTask
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas.auth import LiveSyncMode
from scripts.init.register_webhook_callbacks import register_webhook_callbacks


def _send_task(db: Session) -> MagicMock:
    with patch("app.services.providers.base_strategy.celery_app.send_task") as send_task:
        register_webhook_callbacks(db)
    return send_task


def test_strava_in_webhook_mode_is_registered_again(db: Session) -> None:
    ProviderSettingsRepository().upsert(db, "strava", is_enabled=True, live_sync_mode=LiveSyncMode.WEBHOOK)

    send_task = _send_task(db)

    send_task.assert_called_once()
    assert send_task.call_args.args[0] == CeleryTask.RECONCILE_PROVIDER_WEBHOOKS
    assert send_task.call_args.kwargs["args"] == ["strava", LiveSyncMode.WEBHOOK]


def test_strava_in_pull_mode_and_providers_without_a_callback_token_are_left_alone(db: Session) -> None:
    ProviderSettingsRepository().upsert(db, "strava", is_enabled=True, live_sync_mode=LiveSyncMode.PULL)
    ProviderSettingsRepository().upsert(db, "suunto", is_enabled=True, live_sync_mode=LiveSyncMode.WEBHOOK)

    _send_task(db).assert_not_called()
