"""Tests for WithingsStrategy identity and capabilities."""

from app.schemas.enums import ProviderName
from app.services.providers.factory import ProviderFactory
from app.services.providers.withings.coverage import HEALTH_SCORES, SLEEP_FIELDS, TIMESERIES, WORKOUT_FIELDS
from app.services.providers.withings.data_247 import Withings247Data
from app.services.providers.withings.notify_service import WithingsNotifyService
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


def test_withings_has_user_scoped_webhook_service() -> None:
    strategy = WithingsStrategy()
    assert isinstance(strategy.webhook_service, WithingsNotifyService)
