"""
Tests for seed data generation endpoints.

Tests cover:
- GET /api/v1/settings/seed/presets - list available presets
- POST /api/v1/settings/seed - dispatch seed data generation task
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import DeveloperFactory
from tests.utils import developer_auth_headers


class TestListPresets:
    """Tests for GET /api/v1/settings/seed/presets."""

    def test_list_presets_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        response = client.get(f"{api_v1_prefix}/settings/seed/presets", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # Each preset should have required fields
        preset = data[0]
        assert "id" in preset
        assert "label" in preset
        assert "description" in preset
        assert "profile" in preset

    def test_list_presets_contains_known_ids(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        response = client.get(f"{api_v1_prefix}/settings/seed/presets", headers=headers)

        data = response.json()
        preset_ids = {p["id"] for p in data}
        assert "active_athlete" in preset_ids
        assert "minimal" in preset_ids
        assert "sleep_only" in preset_ids

    def test_list_presets_requires_auth(self, client: TestClient, api_v1_prefix: str) -> None:
        response = client.get(f"{api_v1_prefix}/settings/seed/presets")
        assert response.status_code == 401


class TestDispatchSeedGeneration:
    """Tests for POST /api/v1/settings/seed."""

    @patch("app.api.routes.v1.seed_data.generate_seed_data")
    def test_dispatch_default_config(
        self, mock_task: MagicMock, client: TestClient, db: Session, api_v1_prefix: str
    ) -> None:
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        mock_result = MagicMock()
        mock_result.id = "test-task-id-123"
        mock_task.delay.return_value = mock_result

        response = client.post(
            f"{api_v1_prefix}/settings/seed",
            json={"num_users": 1, "profile": {}},
            headers=headers,
        )

        assert response.status_code == 202
        data = response.json()
        assert data["task_id"] == "test-task-id-123"
        assert data["status"] == "dispatched"
        mock_task.delay.assert_called_once()

    @patch("app.api.routes.v1.seed_data.generate_seed_data")
    def test_dispatch_with_preset_profile(
        self, mock_task: MagicMock, client: TestClient, db: Session, api_v1_prefix: str
    ) -> None:
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        mock_result = MagicMock()
        mock_result.id = "task-456"
        mock_task.delay.return_value = mock_result

        response = client.post(
            f"{api_v1_prefix}/settings/seed",
            json={
                "num_users": 3,
                "profile": {
                    "preset": "active_athlete",
                    "generate_workouts": True,
                    "generate_sleep": False,
                    "generate_time_series": True,
                    "workout_config": {
                        "count": 50,
                        "workout_types": ["running", "boxing"],
                    },
                },
            },
            headers=headers,
        )

        assert response.status_code == 202
        call_args = mock_task.delay.call_args[0][0]
        assert call_args["num_users"] == 3
        assert call_args["profile"]["generate_sleep"] is False
        assert call_args["profile"]["workout_config"]["count"] == 50

    def test_dispatch_requires_auth(self, client: TestClient, api_v1_prefix: str) -> None:
        response = client.post(
            f"{api_v1_prefix}/settings/seed",
            json={"num_users": 1, "profile": {}},
        )
        assert response.status_code == 401

    @patch("app.api.routes.v1.seed_data.generate_seed_data")
    def test_dispatch_validates_num_users(
        self, mock_task: MagicMock, client: TestClient, db: Session, api_v1_prefix: str
    ) -> None:
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        response = client.post(
            f"{api_v1_prefix}/settings/seed",
            json={"num_users": 0, "profile": {}},
            headers=headers,
        )
        assert response.status_code in (400, 422)

        response = client.post(
            f"{api_v1_prefix}/settings/seed",
            json={"num_users": 11, "profile": {}},
            headers=headers,
        )
        assert response.status_code in (400, 422)
