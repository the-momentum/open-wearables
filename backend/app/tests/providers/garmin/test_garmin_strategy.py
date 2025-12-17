"""Tests for Garmin strategy."""


from app.services.providers.garmin.oauth import GarminOAuth
from app.services.providers.garmin.strategy import GarminStrategy
from app.services.providers.garmin.workouts import GarminWorkouts


class TestGarminStrategy:
    """Tests for GarminStrategy class."""

    def test_name_is_garmin(self):
        """Strategy name should be 'garmin'."""
        strategy = GarminStrategy()
        assert strategy.name == "garmin"

    def test_api_base_url(self):
        """API base URL should be Garmin's API endpoint."""
        strategy = GarminStrategy()
        assert strategy.api_base_url == "https://apis.garmin.com"

    def test_display_name(self):
        """Display name should be capitalized provider name."""
        strategy = GarminStrategy()
        assert strategy.display_name == "Garmin"

    def test_has_cloud_api(self):
        """Garmin should have cloud API support."""
        strategy = GarminStrategy()
        assert strategy.has_cloud_api is True

    def test_icon_url(self):
        """Icon URL should point to Garmin SVG icon."""
        strategy = GarminStrategy()
        assert strategy.icon_url == "/static/provider-icons/garmin.svg"

    def test_oauth_component_initialized(self):
        """OAuth component should be initialized."""
        strategy = GarminStrategy()
        assert strategy.oauth is not None
        assert isinstance(strategy.oauth, GarminOAuth)

    def test_workouts_component_initialized(self):
        """Workouts component should be initialized."""
        strategy = GarminStrategy()
        assert strategy.workouts is not None
        assert isinstance(strategy.workouts, GarminWorkouts)

    def test_oauth_has_correct_provider_name(self):
        """OAuth component should have correct provider name."""
        strategy = GarminStrategy()
        assert strategy.oauth.provider_name == "garmin"

    def test_oauth_has_correct_api_base_url(self):
        """OAuth component should have correct API base URL."""
        strategy = GarminStrategy()
        assert strategy.oauth.api_base_url == "https://apis.garmin.com"

    def test_workouts_has_correct_provider_name(self):
        """Workouts component should have correct provider name."""
        strategy = GarminStrategy()
        assert strategy.workouts.provider_name == "garmin"

    def test_workouts_has_correct_api_base_url(self):
        """Workouts component should have correct API base URL."""
        strategy = GarminStrategy()
        assert strategy.workouts.api_base_url == "https://apis.garmin.com"

    def test_repositories_initialized(self):
        """All required repositories should be initialized."""
        strategy = GarminStrategy()
        assert strategy.user_repo is not None
        assert strategy.connection_repo is not None
        assert strategy.workout_repo is not None
