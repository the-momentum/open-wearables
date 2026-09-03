"""Tests for Zepp provider strategy."""

from app.schemas.enums import ProviderName
from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.factory import ProviderFactory
from app.services.providers.zepp.coverage import HEALTH_SCORES, SLEEP_FIELDS, TIMESERIES, WORKOUT_FIELDS
from app.services.providers.zepp.strategy import ZeppStrategy


class TestZeppStrategy:
    """Test suite for ZeppStrategy."""

    def test_zepp_strategy_initialization(self) -> None:
        """Should initialize ZeppStrategy successfully."""
        strategy = ZeppStrategy()

        assert isinstance(strategy, BaseProviderStrategy)
        assert isinstance(strategy, ZeppStrategy)
        assert strategy.name == ProviderName.ZEPP.value
        assert strategy.display_name == "Amazfit / Zepp"
        assert strategy.oauth is None
        assert strategy.has_cloud_api is True
        assert strategy.icon_url == "/static/provider-icons/zepp.svg"

    def test_zepp_strategy_capabilities(self) -> None:
        """Should declare rest_pull=True and max_historical_days=365."""
        strategy = ZeppStrategy()
        caps = strategy.capabilities

        assert caps.rest_pull is True
        assert caps.max_historical_days == 365
        assert caps.webhook_stream is False
        assert caps.webhook_ping is False

    def test_zepp_strategy_coverage(self) -> None:
        """Should expose coverage declared in coverage.py."""
        strategy = ZeppStrategy()
        cov = strategy.coverage

        assert cov.timeseries == TIMESERIES
        assert cov.workout_fields == WORKOUT_FIELDS
        assert cov.sleep_fields == SLEEP_FIELDS
        assert cov.health_scores == HEALTH_SCORES

    def test_zepp_factory_registration(self) -> None:
        """Should resolve ZeppStrategy from ProviderFactory."""
        factory = ProviderFactory()
        provider = factory.get_provider("zepp")

        assert isinstance(provider, ZeppStrategy)
