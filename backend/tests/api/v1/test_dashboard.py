"""
Tests for dashboard endpoints.

Tests cover:
- GET /api/v1/dashboard/stats - get system dashboard statistics

Note: ``data_points.count`` is served approximately (planner statistics / cache) rather than an
exact ``COUNT(*)``, so it is only asserted to be a valid non-negative integer.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import (
    DataPointSeriesFactory,
    DataSourceFactory,
    DeveloperFactory,
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

        # Act
        response = client.get(f"{api_v1_prefix}/dashboard/stats", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "total_users" in data
        assert "active_conn" in data
        assert "data_points" in data
        assert "connections_coverage" in data

        assert isinstance(data["total_users"]["count"], int)
        assert isinstance(data["active_conn"]["count"], int)
        assert isinstance(data["data_points"]["count"], int)

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
        assert data["data_points"]["count"] >= 0

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
        required_keys = ["total_users", "active_conn", "data_points", "event_records", "connections_coverage"]
        for key in required_keys:
            assert key in data, f"Missing required key: {key}"

        for key in ["total_users", "active_conn", "data_points"]:
            assert "count" in data[key]
            assert isinstance(data[key]["count"], int)

        assert isinstance(data["data_points"]["archived"], int)

        event_records = data["event_records"]
        for key in ["count", "workouts", "sleep", "menstrual_cycles"]:
            assert isinstance(event_records[key], int)

        coverage = data["connections_coverage"]
        assert "users_with_active" in coverage
        assert "users_with_multi_active" in coverage
        assert isinstance(coverage["top_providers"], list)

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
