import pytest

from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.sensorbio.data_247 import SensorBio247Data
from app.services.providers.sensorbio.oauth import SensorBioOAuth
from app.services.providers.sensorbio.strategy import SensorBioStrategy
from app.services.providers.sensorbio.workouts import SensorBioWorkouts


class TestSensorBioStrategy:
    @pytest.fixture
    def strategy(self) -> SensorBioStrategy:
        return SensorBioStrategy()

    def test_inherits_base_strategy(self, strategy: SensorBioStrategy) -> None:
        assert isinstance(strategy, BaseProviderStrategy)

    def test_name(self, strategy: SensorBioStrategy) -> None:
        assert strategy.name == "sensorbio"

    def test_api_base_url(self, strategy: SensorBioStrategy) -> None:
        assert strategy.api_base_url == "https://api.sensorbio.com"

    def test_display_name(self, strategy: SensorBioStrategy) -> None:
        assert strategy.display_name == "Sensor Bio"

    def test_has_cloud_api(self, strategy: SensorBioStrategy) -> None:
        assert strategy.has_cloud_api is True

    def test_has_oauth(self, strategy: SensorBioStrategy) -> None:
        assert isinstance(strategy.oauth, SensorBioOAuth)

    def test_has_workouts(self, strategy: SensorBioStrategy) -> None:
        assert isinstance(strategy.workouts, SensorBioWorkouts)

    def test_has_data_247(self, strategy: SensorBioStrategy) -> None:
        assert isinstance(strategy.data_247, SensorBio247Data)
