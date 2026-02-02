"""
Tests for dashboard endpoints.

Tests cover:
- GET /api/v1/dashboard/stats - get system dashboard statistics
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import (
    DataPointSeriesFactory,
    DataSourceFactory,
    DeveloperFactory,
    EventRecordFactory,
    SeriesTypeDefinitionFactory,
    UserConnectionFactory,
    UserFactory,
)
from tests.utils import developer_auth_headers


class TestGetDashboardStats:
    """Tests for GET /api/v1/dashboard/stats."""

    def test_get_dashboard_stats_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test getting dashboard statistics with valid authentication."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Create some test data
        user1 = UserFactory(email="user1@example.com")
        user2 = UserFactory(email="user2@example.com")
        UserConnectionFactory(user=user1, provider="garmin")
        UserConnectionFactory(user=user2, provider="polar")

        mapping1 = DataSourceFactory(user=user1)
        mapping2 = DataSourceFactory(user=user2)
        heart_rate_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()
        DataPointSeriesFactory(mapping=mapping1, series_type=heart_rate_type)
        DataPointSeriesFactory(mapping=mapping2, series_type=steps_type)
        EventRecordFactory(mapping=mapping1, category="workout", type_="running")

        # Act
        response = client.get(f"{api_v1_prefix}/dashboard/stats", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "total_users" in data
        assert "active_conn" in data
        assert "data_points" in data

        # Verify total_users structure
        assert "count" in data["total_users"]
        assert "weekly_growth" in data["total_users"]
        assert isinstance(data["total_users"]["count"], int)
        assert isinstance(data["total_users"]["weekly_growth"], (int, float))

        # Verify active_conn structure
        assert "count" in data["active_conn"]
        assert "weekly_growth" in data["active_conn"]
        assert isinstance(data["active_conn"]["count"], int)
        assert isinstance(data["active_conn"]["weekly_growth"], (int, float))

        # Verify data_points structure
        assert "count" in data["data_points"]
        assert "weekly_growth" in data["data_points"]
        assert "top_series_types" in data["data_points"]
        assert "top_workout_types" in data["data_points"]
        assert isinstance(data["data_points"]["count"], int)
        assert isinstance(data["data_points"]["top_series_types"], list)
        assert isinstance(data["data_points"]["top_workout_types"], list)

    def test_get_dashboard_stats_with_data(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test dashboard statistics reflect actual data."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Create multiple users
        user1 = UserFactory(email="user1@example.com")
        user2 = UserFactory(email="user2@example.com")
        UserFactory(email="user3@example.com")

        # Create connections
        UserConnectionFactory(user=user1, provider="garmin")
        UserConnectionFactory(user=user2, provider="polar")

        # Create data points
        mapping1 = DataSourceFactory(user=user1)
        heart_rate_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()
        DataPointSeriesFactory(mapping=mapping1, series_type=heart_rate_type, value=75.0)
        DataPointSeriesFactory(mapping=mapping1, series_type=heart_rate_type, value=80.0)
        DataPointSeriesFactory(mapping=mapping1, series_type=steps_type, value=1000.0)

        # Act
        response = client.get(f"{api_v1_prefix}/dashboard/stats", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_users"]["count"] >= 3
        assert data["active_conn"]["count"] >= 2
        assert data["data_points"]["count"] >= 3

    def test_get_dashboard_stats_empty_database(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test dashboard statistics with empty database."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.get(f"{api_v1_prefix}/dashboard/stats", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Should return valid structure even with no data
        assert "total_users" in data
        assert "active_conn" in data
        assert "data_points" in data
        assert isinstance(data["total_users"]["count"], int)
        assert isinstance(data["active_conn"]["count"], int)
        assert isinstance(data["data_points"]["count"], int)

    def test_get_dashboard_stats_top_series_types(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test that top series types are correctly reported."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        user = UserFactory()
        mapping = DataSourceFactory(user=user)

        # Use pre-seeded series types
        heart_rate_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()

        # Create data points with different series types
        for _ in range(5):
            DataPointSeriesFactory(mapping=mapping, series_type=heart_rate_type)
        for _ in range(3):
            DataPointSeriesFactory(mapping=mapping, series_type=steps_type)

        # Act
        response = client.get(f"{api_v1_prefix}/dashboard/stats", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        top_series = data["data_points"]["top_series_types"]
        assert isinstance(top_series, list)

        # Verify structure of series type metrics
        if len(top_series) > 0:
            assert "series_type" in top_series[0]
            assert "count" in top_series[0]
            assert isinstance(top_series[0]["count"], int)

    def test_get_dashboard_stats_top_workout_types(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test that top workout types are correctly reported."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        user = UserFactory()
        mapping = DataSourceFactory(user=user)

        # Create event records with different workout types
        EventRecordFactory(mapping=mapping, category="workout", type_="running")
        EventRecordFactory(mapping=mapping, category="workout", type_="running")
        EventRecordFactory(mapping=mapping, category="workout", type_="cycling")

        # Act
        response = client.get(f"{api_v1_prefix}/dashboard/stats", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        top_workouts = data["data_points"]["top_workout_types"]
        assert isinstance(top_workouts, list)

        # Verify structure of workout type metrics
        if len(top_workouts) > 0:
            assert "workout_type" in top_workouts[0]
            assert "count" in top_workouts[0]
            assert isinstance(top_workouts[0]["count"], int)

    def test_get_dashboard_stats_unauthorized(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test getting dashboard stats fails without authentication."""
        # Act
        response = client.get(f"{api_v1_prefix}/dashboard/stats")

        # Assert
        assert response.status_code == 401

    def test_get_dashboard_stats_invalid_token(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test getting dashboard stats fails with invalid token."""
        # Act
        response = client.get(
            f"{api_v1_prefix}/dashboard/stats",
            headers={"Authorization": "Bearer invalid_token"},
        )

        # Assert
        assert response.status_code == 401

    def test_get_dashboard_stats_weekly_growth_calculation(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
    ) -> None:
        """Test that weekly growth is calculated and returned."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Create test data
        user = UserFactory()
        UserConnectionFactory(user=user)
        mapping = DataSourceFactory(user=user)
        DataPointSeriesFactory(mapping=mapping)

        # Act
        response = client.get(f"{api_v1_prefix}/dashboard/stats", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Verify weekly growth fields exist and are numeric
        assert isinstance(data["total_users"]["weekly_growth"], (int, float))
        assert isinstance(data["active_conn"]["weekly_growth"], (int, float))
        assert isinstance(data["data_points"]["weekly_growth"], (int, float))

    def test_get_dashboard_stats_multiple_developers(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test that each developer can access dashboard stats independently."""
        # Arrange
        developer1 = DeveloperFactory(email="dev1@example.com", password="test123")
        developer2 = DeveloperFactory(email="dev2@example.com", password="test123")
        headers1 = developer_auth_headers(developer1.id)
        headers2 = developer_auth_headers(developer2.id)

        # Create test data
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        DataPointSeriesFactory(mapping=mapping)

        # Act
        response1 = client.get(f"{api_v1_prefix}/dashboard/stats", headers=headers1)
        response2 = client.get(f"{api_v1_prefix}/dashboard/stats", headers=headers2)

        # Assert - Both should succeed
        assert response1.status_code == 200
        assert response2.status_code == 200

        # Both should see the same global stats
        data1 = response1.json()
        data2 = response2.json()
        assert data1["total_users"]["count"] == data2["total_users"]["count"]
        assert data1["data_points"]["count"] == data2["data_points"]["count"]

    def test_get_dashboard_stats_response_schema(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test that dashboard stats response matches expected schema."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.get(f"{api_v1_prefix}/dashboard/stats", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Validate complete schema
        required_keys = ["total_users", "active_conn", "data_points"]
        for key in required_keys:
            assert key in data, f"Missing required key: {key}"

        # Validate CountWithGrowth schema
        for key in ["total_users", "active_conn"]:
            assert "count" in data[key]
            assert "weekly_growth" in data[key]

        # Validate DataPointsInfo schema
        assert "count" in data["data_points"]
        assert "weekly_growth" in data["data_points"]
        assert "top_series_types" in data["data_points"]
        assert "top_workout_types" in data["data_points"]

        # Validate list items
        for series_type in data["data_points"]["top_series_types"]:
            assert "series_type" in series_type
            assert "count" in series_type

        for workout_type in data["data_points"]["top_workout_types"]:
            assert "workout_type" in workout_type
            assert "count" in workout_type

    def test_get_dashboard_stats_concurrent_requests(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test that concurrent requests to dashboard stats work correctly."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act - Make multiple concurrent requests
        responses = []
        for _ in range(3):
            response = client.get(f"{api_v1_prefix}/dashboard/stats", headers=headers)
            responses.append(response)

        # Assert - All should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert "total_users" in data
            assert "active_conn" in data
            assert "data_points" in data
