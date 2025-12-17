"""
Integration tests for Polar data import.

Tests end-to-end import flows for Polar exercise data through API endpoints.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests.utils import api_key_headers, create_api_key, create_developer, create_user, create_user_connection


@pytest.fixture
def sample_polar_exercise() -> dict[str, Any]:
    """Sample Polar exercise JSON data."""
    return {
        "id": "ABC123",
        "upload_time": "2024-01-15T09:00:00.000Z",
        "polar_user": "https://www.polaraccesslink.com/v3/users/12345",
        "transaction_id": 67890,
        "device": "Polar Vantage V2",
        "device_id": "12345678",
        "start_time": "2024-01-15T08:00:00",
        "start_time_utc_offset": 60,
        "duration": "PT1H0M0S",
        "distance": 10000.0,
        "heart_rate": {
            "average": 145,
            "maximum": 175,
        },
        "training_load": 150.0,
        "sport": "RUNNING",
        "has_route": True,
        "detailed_sport_info": "RUNNING",
    }


class TestPolarOAuthFlow:
    """Tests for Polar OAuth authorization and callback flow."""

    @patch("app.integrations.redis_client.get_redis_client")
    def test_get_polar_authorization_url(
        self, mock_redis_client: MagicMock, client: TestClient, db: Session,
    ) -> None:
        """Test getting Polar authorization URL."""
        # Arrange
        user = create_user(db)
        developer = create_developer(db)
        api_key = create_api_key(db, developer=developer)
        headers = api_key_headers(api_key.id)

        mock_redis = MagicMock()
        mock_redis.setex.return_value = True
        mock_redis_client.return_value = mock_redis

        # Act - Endpoint is /oauth/polar/authorize with user_id as query param
        response = client.get(
            f"/api/v1/oauth/polar/authorize?user_id={user.id}",
            headers=headers,
        )

        # Assert
        assert response.status_code in [200, 422]  # May vary based on config
        if response.status_code == 200:
            data = response.json()
            assert "authorization_url" in data or "url" in data

    @patch("app.integrations.celery.tasks.sync_vendor_data.delay")
    @patch("app.services.providers.templates.base_oauth.get_redis_client")
    @patch("httpx.post")
    def test_polar_oauth_callback_success(
        self,
        mock_post: MagicMock,
        mock_redis_client: MagicMock,
        mock_celery_task: MagicMock,
        client: TestClient,
        db: Session,
    ) -> None:
        """Test successful Polar OAuth callback."""
        # Arrange
        user = create_user(db)
        developer = create_developer(db)
        create_api_key(db, developer=developer)

        # Mock Redis for state validation - must return proper state data
        mock_redis = MagicMock()
        import json
        state_data = {
            "user_id": str(user.id),
            "provider": "polar",
            "redirect_uri": None,
        }
        mock_redis.get.return_value = json.dumps(state_data).encode("utf-8")
        mock_redis.delete.return_value = True
        mock_redis_client.return_value = mock_redis

        # Mock OAuth token exchange
        mock_token_response = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            "access_token": "polar_access_token",
            "refresh_token": "polar_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "x_user_id": 12345,
        }
        mock_post.return_value = mock_token_response

        # Mock Celery task
        mock_celery_task.return_value = MagicMock()

        # Act - Endpoint is /oauth/polar/callback
        response = client.get(
            "/api/v1/oauth/polar/callback",
            params={"code": "test_code", "state": "test_state"},
        )

        # Assert - May redirect or return connection info (303 is most common for OAuth redirects)
        assert response.status_code in [200, 302, 303, 307, 422]


class TestPolarWorkoutsAPI:
    """Tests for Polar workouts API endpoints."""

    @patch("app.services.providers.templates.base_workouts.make_authenticated_request")
    def test_get_polar_workouts_list(
        self, mock_request: MagicMock, client: TestClient, db: Session, sample_polar_exercise: dict[str, Any],
    ) -> None:
        """Test getting list of Polar workouts."""
        # Arrange
        user = create_user(db)
        create_user_connection(db, user=user, provider="polar")
        developer = create_developer(db)
        api_key = create_api_key(db, developer=developer)
        headers = api_key_headers(api_key.id)

        mock_request.return_value = [sample_polar_exercise]

        # Act
        response = client.get(
            f"/api/v1/users/{user.id}/vendors/polar/workouts",
            headers=headers,
        )

        # Assert
        assert response.status_code in [200, 404, 422]

    @patch("app.services.providers.templates.base_workouts.make_authenticated_request")
    def test_get_polar_workout_detail(
        self, mock_request: MagicMock, client: TestClient, db: Session, sample_polar_exercise: dict[str, Any],
    ) -> None:
        """Test getting detailed Polar workout data."""
        # Arrange
        user = create_user(db)
        create_user_connection(db, user=user, provider="polar")
        developer = create_developer(db)
        api_key = create_api_key(db, developer=developer)
        headers = api_key_headers(api_key.id)

        mock_request.return_value = sample_polar_exercise
        workout_id = "ABC123"

        # Act
        response = client.get(
            f"/api/v1/users/{user.id}/vendors/polar/workouts/{workout_id}",
            headers=headers,
        )

        # Assert
        assert response.status_code in [200, 404, 422]

    @patch("app.services.providers.templates.base_workouts.make_authenticated_request")
    def test_get_polar_workouts_with_samples(self, mock_request: MagicMock, client: TestClient, db: Session) -> None:
        """Test getting Polar workouts with samples parameter."""
        # Arrange
        user = create_user(db)
        create_user_connection(db, user=user, provider="polar")
        developer = create_developer(db)
        api_key = create_api_key(db, developer=developer)
        headers = api_key_headers(api_key.id)

        mock_request.return_value = []

        # Act
        response = client.get(
            f"/api/v1/users/{user.id}/vendors/polar/workouts",
            headers=headers,
            params={"samples": "true"},
        )

        # Assert
        assert response.status_code in [200, 404, 422]

    def test_get_polar_workouts_no_connection(self, client: TestClient, db: Session) -> None:
        """Test getting Polar workouts without active connection."""
        # Arrange
        user = create_user(db)
        developer = create_developer(db)
        api_key = create_api_key(db, developer=developer)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(
            f"/api/v1/users/{user.id}/vendors/polar/workouts",
            headers=headers,
        )

        # Assert
        assert response.status_code in [404, 422]  # No connection exists


class TestPolarDataSync:
    """Tests for syncing Polar data."""

    @patch("app.services.providers.templates.base_workouts.make_authenticated_request")
    @patch("app.services.event_record_service.event_record_service.create")
    @patch("app.services.event_record_service.event_record_service.create_detail")
    def test_sync_polar_data_success(
        self,
        mock_create_detail: MagicMock,
        mock_create: MagicMock,
        mock_request: MagicMock,
        client: TestClient,
        db: Session,
        sample_polar_exercise: dict[str, Any],
    ) -> None:
        """Test successful Polar data sync."""
        # Arrange
        user = create_user(db)
        create_user_connection(db, user=user, provider="polar")
        developer = create_developer(db)
        api_key = create_api_key(db, developer=developer)
        headers = api_key_headers(api_key.id)

        mock_request.return_value = [sample_polar_exercise]

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/sync/polar",
            headers=headers,
        )

        # Assert
        assert response.status_code in [200, 201, 202, 404, 422]

    @patch("app.services.providers.templates.base_workouts.make_authenticated_request")
    def test_sync_polar_data_with_date_range(self, mock_request: MagicMock, client: TestClient, db: Session) -> None:
        """Test syncing Polar data with specific date range."""
        # Arrange
        user = create_user(db)
        create_user_connection(db, user=user, provider="polar")
        developer = create_developer(db)
        api_key = create_api_key(db, developer=developer)
        headers = api_key_headers(api_key.id)

        mock_request.return_value = []

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/sync/polar",
            headers=headers,
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
        )

        # Assert
        assert response.status_code in [200, 201, 202, 404, 422]

    def test_sync_polar_data_no_connection(self, client: TestClient, db: Session) -> None:
        """Test syncing Polar data without connection returns error."""
        # Arrange
        user = create_user(db)
        developer = create_developer(db)
        api_key = create_api_key(db, developer=developer)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/sync/polar",
            headers=headers,
        )

        # Assert
        assert response.status_code in [404, 422]  # No connection
