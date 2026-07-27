"""Tests for the /users/{user_id}/timeseries endpoint resolution parameter."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import (
    ApiKeyFactory,
    DataPointSeriesFactory,
    DataSourceFactory,
    SeriesTypeDefinitionFactory,
    UserFactory,
)
from tests.utils import api_key_headers


class TestTimeseriesResolution:
    """The endpoint must honor the resolution query parameter."""

    def test_resolution_defaults_to_raw(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        recorded_at = datetime(2024, 1, 1, 10, 0, 13, tzinfo=timezone.utc)
        DataPointSeriesFactory(mapping=mapping, series_type=hr_type, recorded_at=recorded_at, value=66)

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/timeseries",
            headers=api_key_headers(api_key.id),
            params={"start_time": "2024-01-01T00:00:00Z", "end_time": "2024-01-02T00:00:00Z"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert len(payload["data"]) == 1
        assert payload["data"][0]["timestamp"] == "2024-01-01T10:00:13Z"
        assert payload["metadata"]["resolution"] is None

    def test_resolution_is_forwarded_and_downsamples(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        for seconds, value in [(5, 60), (25, 90), (45, 90)]:
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=hr_type,
                recorded_at=datetime(2024, 1, 1, 10, 0, seconds, tzinfo=timezone.utc),
                value=value,
            )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/timeseries",
            headers=api_key_headers(api_key.id),
            params={
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-02T00:00:00Z",
                "resolution": "1min",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert len(payload["data"]) == 1
        assert payload["data"][0]["timestamp"] == "2024-01-01T10:00:00Z"
        assert payload["data"][0]["value"] == 80.0
        assert payload["metadata"]["resolution"] == "1min"

    def test_invalid_resolution_is_rejected(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/timeseries",
            headers=api_key_headers(api_key.id),
            params={
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-02T00:00:00Z",
                "resolution": "42min",
            },
        )

        assert response.status_code == 400
