"""Tests for WithingsStrategy identity and capabilities."""

from unittest.mock import patch
from uuid import uuid4

from app.schemas.auth import LiveSyncMode
from app.schemas.enums import ProviderName
from app.services.providers.factory import ProviderFactory
from app.services.providers.suunto.strategy import SuuntoStrategy
from app.services.providers.withings.coverage import HEALTH_SCORES, SLEEP_FIELDS, TIMESERIES, WORKOUT_FIELDS
from app.services.providers.withings.data_247 import Withings247Data
from app.services.providers.withings.strategy import WithingsStrategy


def test_factory_returns_withings_strategy() -> None:
    strategy = ProviderFactory().get_provider(ProviderName.WITHINGS.value)
    assert isinstance(strategy, WithingsStrategy)


def test_withings_identity_and_capabilities() -> None:
    strategy = WithingsStrategy()
    assert strategy.name == "withings"
    assert strategy.api_base_url == "https://wbsapi.withings.net"
    caps = strategy.capabilities
    assert caps.rest_pull is True
    assert caps.webhook_ping is True
    assert caps.webhook_registration_api is False  # per-user, not app-level
    assert caps.webhook_per_user_subscriptions is True
    # rest_pull + webhook_ping ⇒ live sync mode is admin-configurable
    assert strategy.live_sync_configurable is True


def test_live_sync_subscription_task_maps_mode_to_per_user_task() -> None:
    strategy = WithingsStrategy()
    assert strategy.live_sync_subscription_task(LiveSyncMode.WEBHOOK).endswith("subscribe_withings_user")
    assert strategy.live_sync_subscription_task(LiveSyncMode.PULL).endswith("revoke_withings_user")


def test_withings_exposes_coverage_for_report() -> None:
    coverage = WithingsStrategy().coverage
    assert coverage.timeseries == TIMESERIES
    assert coverage.workout_fields == WORKOUT_FIELDS
    assert coverage.sleep_fields == SLEEP_FIELDS
    assert coverage.health_scores == HEALTH_SCORES


def test_withings_has_oauth_component() -> None:
    strategy = WithingsStrategy()
    assert strategy.oauth is not None


def test_withings_has_data_247_component() -> None:
    strategy = WithingsStrategy()
    assert isinstance(strategy.data_247, Withings247Data)


def test_on_connect_enqueues_subscription_task_when_webhook_mode() -> None:
    """Withings registers per-user notify subscriptions only in webhook mode."""
    strategy = WithingsStrategy()
    user_id = uuid4()
    with (
        patch("app.services.providers.withings.strategy.SessionLocal"),
        patch.object(strategy, "effective_live_sync_mode", return_value=LiveSyncMode.WEBHOOK),
        patch("app.services.providers.withings.strategy.celery_app") as celery_app,
    ):
        strategy.on_connect(user_id)
    celery_app.send_task.assert_called_once_with(
        "app.integrations.celery.tasks.withings.subscribe_task.subscribe_withings_user",
        args=[str(user_id)],
        queue="webhook_sync",
    )


def test_on_connect_does_not_subscribe_in_pull_mode() -> None:
    strategy = WithingsStrategy()
    with (
        patch("app.services.providers.withings.strategy.SessionLocal"),
        patch.object(strategy, "effective_live_sync_mode", return_value=LiveSyncMode.PULL),
        patch("app.services.providers.withings.strategy.celery_app") as celery_app,
    ):
        strategy.on_connect(uuid4())
    celery_app.send_task.assert_not_called()


def test_on_connect_default_is_noop() -> None:
    """Providers without post-connect side effects inherit a no-op."""
    SuuntoStrategy().on_connect(uuid4())  # must not raise
