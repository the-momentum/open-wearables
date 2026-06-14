"""Tests for WithingsStrategy identity and capabilities."""

from unittest.mock import patch
from uuid import uuid4

from app.schemas.enums import ProviderName
from app.services.providers.factory import ProviderFactory
from app.services.providers.suunto.strategy import SuuntoStrategy
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
    # rest_pull + webhook_ping ⇒ live sync mode is admin-configurable
    assert strategy.live_sync_configurable is True


def test_withings_has_oauth_component() -> None:
    strategy = WithingsStrategy()
    assert strategy.oauth is not None


def test_withings_has_data_247_component() -> None:
    strategy = WithingsStrategy()
    assert isinstance(strategy.data_247, Withings247Data)


def test_on_connect_enqueues_subscription_task() -> None:
    """Withings registers its per-user notify subscriptions on connect."""
    strategy = WithingsStrategy()
    user_id = uuid4()
    with patch("app.services.providers.withings.strategy.celery_app") as celery_app:
        strategy.on_connect(user_id)
    celery_app.send_task.assert_called_once_with(
        "app.integrations.celery.tasks.withings.subscribe_task.subscribe_withings_user",
        args=[str(user_id)],
    )


def test_on_connect_default_is_noop() -> None:
    """Providers without post-connect side effects inherit a no-op."""
    SuuntoStrategy().on_connect(uuid4())  # must not raise
