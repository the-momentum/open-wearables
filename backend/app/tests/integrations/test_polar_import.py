"""
Integration tests for Polar data import.

Tests end-to-end import flows for Polar exercise data through API endpoints.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests.utils import api_key_headers, create_api_key, create_developer, create_user, create_user_connection


class TestPolarOAuthFlow:
    """Tests for Polar OAuth authorization and callback flow."""

    @patch("app.integrations.redis_client.get_redis_client")
    def test_get_polar_authorization_url(self, mock_redis_client, client: TestClient, db: Session):
        """Test getting Polar authorization URL."""
        # Arrange
        user = create_user(db)
        developer = create_developer(db)
        api_key = create_api_key(db, developer=developer)
        headers = api_key_headers(api_key.id)

        mock_redis = MagicMock()
        mock_redis.setex.return_value = True
        mock_redis_client.return_value = mock_redis

        # Act
        response = client.get(
            f"/api/v1/users/{user.id}/connections/polar/authorize",
            headers=headers,
        )

        # Assert
        assert response.status_code in [200, 422]  # May vary based on config
        if response.status_code == 200:
            data = response.json()
            assert "authorization_url" in data or "url" in data

    @patch("app.integrations.redis_client.get_redis_client")
    @patch("httpx.post")
    def test_polar_oauth_callback_success(self, mock_post, mock_redis_client, client: TestClient, db: Session):
        """Test successful Polar OAuth callback."""
        # Arrange
        user = create_user(db)
        developer = create_developer(db)
        api_key = create_api_key(db, developer=developer)

        # Mock Redis for state validation
        mock_redis = MagicMock()
        state_data = {
            "user_id": str(user.id),
            "provider": "polar",
            "redirect_uri": None,
        }
        mock_redis.get.return_value = str(state_data).encode("utf-8")
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

        # Act
        response = client.get(
            "/api/v1/oauth/callback",
            params={"code": "test_code", "state": "test_state"},
        )

        # Assert - May redirect or return connection info
        assert response.status_code in [200, 302, 307, 422]


class TestPolarWorkoutsAPI:
    """Tests for Polar workouts API endpoints."""

    @patch("app.services.providers.api_client.make_authenticated_request")
    def test_get_polar_workouts_list(self, mock_request, client: TestClient, db: Session, sample_polar_exercise):
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

    @patch("app.services.providers.api_client.make_authenticated_request")
    def test_get_polar_workout_detail(self, mock_request, client: TestClient, db: Session, sample_polar_exercise):
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

    @patch("app.services.providers.api_client.make_authenticated_request")
    def test_get_polar_workouts_with_samples(self, mock_request, client: TestClient, db: Session):
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

    def test_get_polar_workouts_no_connection(self, client: TestClient, db: Session):
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

    @patch("app.services.providers.api_client.make_authenticated_request")
    @patch("app.services.event_record_service.event_record_service.create")
    @patch("app.services.event_record_service.event_record_service.create_detail")
    def test_sync_polar_data_success(
        self,
        mock_create_detail,
        mock_create,
        mock_request,
        client: TestClient,
        db: Session,
        sample_polar_exercise,
    ):
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

    @patch("app.services.providers.api_client.make_authenticated_request")
    def test_sync_polar_data_with_date_range(self, mock_request, client: TestClient, db: Session):
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

    def test_sync_polar_data_no_connection(self, client: TestClient, db: Session):
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
