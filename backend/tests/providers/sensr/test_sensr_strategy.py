import pytest

from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.sensr.data_247 import Sensr247Data
from app.services.providers.sensr.oauth import SensrOAuth
from app.services.providers.sensr.strategy import SensrStrategy
from app.services.providers.sensr.workouts import SensrWorkouts


class TestSensrStrategy:
    @pytest.fixture
    def strategy(self) -> SensrStrategy:
        return SensrStrategy()

    def test_inherits_base_strategy(self, strategy: SensrStrategy) -> None:
        assert isinstance(strategy, BaseProviderStrategy)

    def test_name(self, strategy: SensrStrategy) -> None:
        assert strategy.name == "sensr"

    def test_api_base_url(self, strategy: SensrStrategy) -> None:
        assert strategy.api_base_url == "https://api.getsensr.io"

    def test_display_name(self, strategy: SensrStrategy) -> None:
        assert strategy.display_name == "Sensor Bio"

    def test_has_cloud_api(self, strategy: SensrStrategy) -> None:
        assert strategy.has_cloud_api is True

    def test_has_oauth(self, strategy: SensrStrategy) -> None:
        assert isinstance(strategy.oauth, SensrOAuth)

    def test_has_workouts(self, strategy: SensrStrategy) -> None:
        assert isinstance(strategy.workouts, SensrWorkouts)

    def test_has_data_247(self, strategy: SensrStrategy) -> None:
        assert isinstance(strategy.data_247, Sensr247Data)
