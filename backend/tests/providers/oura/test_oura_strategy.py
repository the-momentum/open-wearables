"""Tests for OuraStrategy."""

import pytest

from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.oura.data_247 import Oura247Data
from app.services.providers.oura.oauth import OuraOAuth
from app.services.providers.oura.strategy import OuraStrategy
from app.services.providers.oura.workouts import OuraWorkouts


class TestOuraStrategy:
    """Test suite for OuraStrategy."""

    @pytest.fixture
    def strategy(self) -> OuraStrategy:
        return OuraStrategy()

    def test_inherits_base_strategy(self, strategy: OuraStrategy) -> None:
        assert isinstance(strategy, BaseProviderStrategy)

    def test_name(self, strategy: OuraStrategy) -> None:
        assert strategy.name == "oura"

    def test_api_base_url(self, strategy: OuraStrategy) -> None:
        assert strategy.api_base_url == "https://api.ouraring.com"

    def test_display_name(self, strategy: OuraStrategy) -> None:
        assert strategy.display_name == "Oura"

    def test_has_cloud_api(self, strategy: OuraStrategy) -> None:
        assert strategy.has_cloud_api is True

    def test_icon_url(self, strategy: OuraStrategy) -> None:
        assert strategy.icon_url == "/static/provider-icons/oura.svg"

    def test_has_oauth(self, strategy: OuraStrategy) -> None:
        assert strategy.oauth is not None
        assert isinstance(strategy.oauth, OuraOAuth)

    def test_has_workouts(self, strategy: OuraStrategy) -> None:
        assert strategy.workouts is not None
        assert isinstance(strategy.workouts, OuraWorkouts)

    def test_has_data_247(self, strategy: OuraStrategy) -> None:
        assert strategy.data_247 is not None
        assert isinstance(strategy.data_247, Oura247Data)

    def test_has_repositories(self, strategy: OuraStrategy) -> None:
        assert strategy.user_repo is not None
        assert strategy.connection_repo is not None
        assert strategy.workout_repo is not None
