"""Tests for the workouts list endpoint's priority filter."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.enums import ProviderName
from app.services.priority_service import priority_service
from tests.factories import ApiKeyFactory, DataSourceFactory, EventRecordFactory, UserFactory
from tests.utils import api_key_headers


class TestListWorkoutsFilterByPriority:
    """GET /users/{user_id}/events/workouts?filter_by_priority=..."""

    def _seed_duplicate_ride(self, db: Session) -> tuple:
        user = UserFactory()
        strava = DataSourceFactory(user=user, provider="strava", source="strava")
        apple = DataSourceFactory(user=user, provider="apple")
        start = datetime(2026, 4, 10, 8, 0, tzinfo=timezone.utc)
        kwargs = {
            "category": "workout",
            "type_": "cycling",
            "start_datetime": start,
            "end_datetime": start + timedelta(minutes=26),
            "duration_seconds": 26 * 60,
        }
        strava_record = EventRecordFactory(mapping=strava, **kwargs)
        apple_record = EventRecordFactory(mapping=apple, **kwargs)
        priority_service.update_provider_priority(db, ProviderName.STRAVA, 1)
        priority_service.update_provider_priority(db, ProviderName.APPLE, 2)
        return user, strava_record, apple_record

    def _get(self, client: TestClient, user_id: UUID, **extra: str) -> list[str]:
        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user_id}/events/workouts",
            headers=api_key_headers(api_key.plain_key),
            params={"start_date": "2026-04-01T00:00:00Z", "end_date": "2026-04-30T00:00:00Z", **extra},
        )
        assert response.status_code == 200
        return [w["id"] for w in response.json()["data"]]

    def test_returns_every_source_by_default(self, client: TestClient, db: Session) -> None:
        user, strava_record, apple_record = self._seed_duplicate_ride(db)

        ids = self._get(client, user.id)

        assert set(ids) == {str(strava_record.id), str(apple_record.id)}

    def test_filter_by_priority_drops_the_lower_priority_copy(self, client: TestClient, db: Session) -> None:
        user, strava_record, _ = self._seed_duplicate_ride(db)

        ids = self._get(client, user.id, filter_by_priority="true")

        assert ids == [str(strava_record.id)]
