from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.services.providers.factory import ProviderFactory
from app.services.providers.fitbit.oauth import FitbitOAuth
from app.services.providers.fitbit.strategy import FitbitStrategy
from app.services.providers.fitbit.workouts import FitbitWorkouts


def test_factory_returns_fitbit_strategy() -> None:
    factory = ProviderFactory()
    strategy = factory.get_provider("fitbit")
    assert isinstance(strategy, FitbitStrategy)


def test_fitbit_strategy_name() -> None:
    strategy = FitbitStrategy()
    assert strategy.name == "fitbit"


def test_fitbit_strategy_api_base_url() -> None:
    strategy = FitbitStrategy()
    assert strategy.api_base_url == "https://api.fitbit.com"


def test_fitbit_strategy_has_cloud_api() -> None:
    strategy = FitbitStrategy()
    assert strategy.has_cloud_api is True


def test_fitbit_strategy_oauth_is_correct_type() -> None:
    strategy = FitbitStrategy()
    assert isinstance(strategy.oauth, FitbitOAuth)


def test_fitbit_strategy_workouts_is_correct_type() -> None:
    strategy = FitbitStrategy()
    assert isinstance(strategy.workouts, FitbitWorkouts)


def test_fitbit_strategy_oauth_shares_provider_name() -> None:
    strategy = FitbitStrategy()
    assert strategy.oauth.provider_name == "fitbit"


def test_fitbit_strategy_workouts_shares_oauth_instance() -> None:
    strategy = FitbitStrategy()
    assert strategy.workouts.oauth is strategy.oauth


def test_fitbit_strategy_repositories() -> None:
    strategy = FitbitStrategy()
    assert isinstance(strategy.user_repo, UserRepository)
    assert isinstance(strategy.connection_repo, UserConnectionRepository)
    assert isinstance(strategy.workout_repo, EventRecordRepository)
