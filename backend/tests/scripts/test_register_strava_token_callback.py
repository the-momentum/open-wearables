from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.constants.celery_tasks import CeleryTask
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas.auth import LiveSyncMode
from scripts.data_migrations.register_strava_token_callback import register_strava_token_callback


def _send_task(db: Session, mode: LiveSyncMode) -> MagicMock:
    ProviderSettingsRepository().upsert(db, "strava", is_enabled=True, live_sync_mode=mode)
    with patch("app.services.providers.base_strategy.celery_app.send_task") as send_task:
        assert register_strava_token_callback(db)
    return send_task


def test_strava_in_webhook_mode_is_registered_again(db: Session) -> None:
    send_task = _send_task(db, LiveSyncMode.WEBHOOK)

    send_task.assert_called_once()
    assert send_task.call_args.args[0] == CeleryTask.RECONCILE_PROVIDER_WEBHOOKS
    assert send_task.call_args.kwargs["args"] == ["strava", LiveSyncMode.WEBHOOK]


def test_strava_in_pull_mode_is_left_alone(db: Session) -> None:
    _send_task(db, LiveSyncMode.PULL).assert_not_called()


def test_dry_run_queues_nothing(db: Session) -> None:
    ProviderSettingsRepository().upsert(db, "strava", is_enabled=True, live_sync_mode=LiveSyncMode.WEBHOOK)
    with patch("app.services.providers.base_strategy.celery_app.send_task") as send_task:
        assert not register_strava_token_callback(db, dry_run=True)

    send_task.assert_not_called()
