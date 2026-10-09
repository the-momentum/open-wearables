"""Tests for the Hevy provider strategy wiring."""

import pytest

from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.hevy.strategy import HevyStrategy


class TestHevyStrategy:
    @pytest.fixture
    def strategy(self) -> HevyStrategy:
        return HevyStrategy()

    def test_inherits_base(self, strategy: HevyStrategy) -> None:
        assert isinstance(strategy, BaseProviderStrategy)

    def test_identity(self, strategy: HevyStrategy) -> None:
        assert strategy.name == "hevy"
        assert strategy.display_name == "Hevy"
        assert strategy.api_base_url == "https://api.hevyapp.com"
        assert strategy.icon_url == "/static/provider-icons/hevy.svg"

    def test_capabilities(self, strategy: HevyStrategy) -> None:
        caps = strategy.capabilities
        assert caps.rest_pull is True
        assert caps.api_key_connect is True
        assert caps.client_sdk is False
        assert caps.webhook_stream is False
        assert caps.webhook_ping is False

    def test_no_oauth_but_cloud_api(self, strategy: HevyStrategy) -> None:
        # API-key auth: no OAuth template, but the provider does have a cloud API.
        assert strategy.oauth is None
        assert strategy.has_cloud_api is True

    def test_components_wired(self, strategy: HevyStrategy) -> None:
        assert strategy.workouts is not None
        assert strategy.data_247 is None

    def test_coverage(self, strategy: HevyStrategy) -> None:
        cov = strategy.coverage
        assert cov.workout_fields == frozenset({"distance", "segments"})
        assert cov.timeseries == frozenset()
        assert cov.sleep_fields == frozenset()
        assert cov.health_scores == frozenset()
