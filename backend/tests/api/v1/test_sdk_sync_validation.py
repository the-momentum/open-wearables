"""Tests for SDK sync endpoint validation with unknown types.

Verifies that unknown type values in records, sleep, workouts, and workout statistics
are silently filtered out and the endpoint returns 202.
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
def mock_process_apple_upload() -> Generator[MagicMock, None, None]:
    """Mock Celery task to prevent actual task execution."""
    with patch("app.api.routes.v1.sdk_sync.process_apple_upload") as mock:
        mock.delay.return_value = None
        yield mock


class TestSyncWithUnknownTypes:
    """Tests that unknown type values are filtered and the endpoint returns 202."""

    def _post_sync(self, client: TestClient, api_v1_prefix: str, api_key_header: dict, payload: dict) -> object:
        return client.post(
            f"{api_v1_prefix}/sdk/users/test-user-id/sync/apple",
            headers=api_key_header,
            json=payload,
        )

    def test_sync_with_unknown_record_type_returns_202(
        self, client: TestClient, api_v1_prefix: str, api_key_header: dict
    ) -> None:
        payload = {
            "data": {
                "records": [
                    {
                        "uuid": "TEST0001-0000-0000-0000-000000000001",
                        "type": "HKQuantityTypeIdentifierSomeNewAppleType",
                        "startDate": "2025-01-15T10:00:00Z",
                        "endDate": "2025-01-15T10:05:00Z",
                        "unit": "count",
                        "value": 42,
                    }
                ]
            }
        }
        response = self._post_sync(client, api_v1_prefix, api_key_header, payload)
        assert response.status_code == 200

    def test_sync_with_unknown_workout_type_returns_202(
        self, client: TestClient, api_v1_prefix: str, api_key_header: dict
    ) -> None:
        payload = {
            "data": {
                "workouts": [
                    {
                        "uuid": "TEST0002-0000-0000-0000-000000000002",
                        "type": "brand_new_sport",
                        "startDate": "2025-01-15T14:00:00Z",
                        "endDate": "2025-01-15T15:00:00Z",
                        "workoutStatistics": [
                            {"type": "duration", "unit": "s", "value": 3600},
                        ],
                    }
                ]
            }
        }
        response = self._post_sync(client, api_v1_prefix, api_key_header, payload)
        assert response.status_code == 200

    def test_sync_with_unknown_sleep_type_returns_202(
        self, client: TestClient, api_v1_prefix: str, api_key_header: dict
    ) -> None:
        payload = {
            "data": {
                "sleep": [
                    {
                        "uuid": "TEST0003-0000-0000-0000-000000000003",
                        "type": "HKCategoryTypeIdentifierSomeNewSleepType",
                        "startDate": "2025-01-15T22:00:00Z",
                        "endDate": "2025-01-15T22:30:00Z",
                        "unit": None,
                        "value": 3,
                    }
                ]
            }
        }
        response = self._post_sync(client, api_v1_prefix, api_key_header, payload)
        assert response.status_code == 200

    def test_sync_with_unknown_workout_statistic_type_returns_202(
        self, client: TestClient, api_v1_prefix: str, api_key_header: dict
    ) -> None:
        payload = {
            "data": {
                "workouts": [
                    {
                        "uuid": "TEST0004-0000-0000-0000-000000000004",
                        "type": "running",
                        "startDate": "2025-01-15T08:00:00Z",
                        "endDate": "2025-01-15T08:30:00Z",
                        "workoutStatistics": [
                            {"type": "duration", "unit": "s", "value": 1800},
                            {"type": "brandNewStatistic", "unit": "units", "value": 99.9},
                        ],
                    }
                ]
            }
        }
        response = self._post_sync(client, api_v1_prefix, api_key_header, payload)
        assert response.status_code == 200

    def test_sync_with_mix_of_known_and_unknown_types_returns_202(
        self, client: TestClient, api_v1_prefix: str, api_key_header: dict
    ) -> None:
        payload = {
            "data": {
                "records": [
                    {
                        "uuid": "TEST0005-0000-0000-0000-000000000001",
                        "type": "HKQuantityTypeIdentifierHeartRate",
                        "startDate": "2025-01-15T10:00:00Z",
                        "endDate": "2025-01-15T10:01:00Z",
                        "unit": "bpm",
                        "value": 72,
                    },
                    {
                        "uuid": "TEST0005-0000-0000-0000-000000000002",
                        "type": "HKQuantityTypeIdentifierFutureMetric",
                        "startDate": "2025-01-15T10:01:00Z",
                        "endDate": "2025-01-15T10:02:00Z",
                        "unit": "count",
                        "value": 5,
                    },
                ],
                "workouts": [
                    {
                        "uuid": "TEST0005-0000-0000-0000-000000000003",
                        "type": "running",
                        "startDate": "2025-01-15T08:00:00Z",
                        "endDate": "2025-01-15T08:30:00Z",
                        "workoutStatistics": [
                            {"type": "distance", "unit": "m", "value": 5000},
                        ],
                    },
                    {
                        "uuid": "TEST0005-0000-0000-0000-000000000004",
                        "type": "underwater_basket_weaving",
                        "startDate": "2025-01-15T09:00:00Z",
                        "endDate": "2025-01-15T09:45:00Z",
                        "workoutStatistics": [],
                    },
                ],
            }
        }
        response = self._post_sync(client, api_v1_prefix, api_key_header, payload)
        assert response.status_code == 200
