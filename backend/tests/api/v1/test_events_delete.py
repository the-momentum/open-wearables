"""
Tests for event record DELETE endpoints.

Tests the DELETE /api/v1/users/{user_id}/events/workouts/{id}
and DELETE /api/v1/users/{user_id}/events/sleep/{id} endpoints including:
- Successful deletion with cascade (details removed)
- 404 for non-existent records
- 404 for records belonging to another user
- 404 for wrong category (e.g. deleting sleep via workouts endpoint)
"""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import EventRecord, EventRecordDetail
from tests.factories import (
    ApiKeyFactory,
    DataSourceFactory,
    EventRecordFactory,
    SleepDetailsFactory,
    UserFactory,
    WorkoutDetailsFactory,
)
from tests.utils import api_key_headers


class TestDeleteWorkout:
    """Test suite for DELETE /users/{user_id}/events/workouts/{workout_id}."""

    def test_delete_workout_success(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        workout = EventRecordFactory(mapping=ds, category="workout", type_="running")
        WorkoutDetailsFactory(event_record=workout)
        api_key = ApiKeyFactory()

        response = client.delete(
            f"/api/v1/users/{user.id}/events/workouts/{workout.id}",
            headers=api_key_headers(api_key.id),
        )

        assert response.status_code == 204
        assert db.get(EventRecord, workout.id) is None

    def test_delete_workout_cascades_details(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        workout = EventRecordFactory(mapping=ds, category="workout", type_="cycling")
        detail = WorkoutDetailsFactory(event_record=workout)
        detail_record_id = detail.record_id
        api_key = ApiKeyFactory()

        response = client.delete(
            f"/api/v1/users/{user.id}/events/workouts/{workout.id}",
            headers=api_key_headers(api_key.id),
        )

        assert response.status_code == 204
        assert db.get(EventRecord, workout.id) is None
        # Detail should be cascade-deleted
        remaining = db.query(EventRecordDetail).filter(EventRecordDetail.record_id == detail_record_id).first()
        assert remaining is None

    def test_delete_workout_not_found(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        api_key = ApiKeyFactory()

        response = client.delete(
            f"/api/v1/users/{user.id}/events/workouts/{uuid4()}",
            headers=api_key_headers(api_key.id),
        )

        assert response.status_code == 404

    def test_delete_workout_wrong_user(self, client: TestClient, db: Session) -> None:
        owner = UserFactory()
        other_user = UserFactory()
        ds = DataSourceFactory(user=owner)
        workout = EventRecordFactory(mapping=ds, category="workout", type_="running")
        api_key = ApiKeyFactory()

        response = client.delete(
            f"/api/v1/users/{other_user.id}/events/workouts/{workout.id}",
            headers=api_key_headers(api_key.id),
        )

        assert response.status_code == 404
        # Record should still exist
        assert db.get(EventRecord, workout.id) is not None

    def test_delete_workout_wrong_category(self, client: TestClient, db: Session) -> None:
        """Deleting a sleep record via workouts endpoint should return 404."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        sleep = EventRecordFactory(mapping=ds, category="sleep", type="sleep")
        api_key = ApiKeyFactory()

        response = client.delete(
            f"/api/v1/users/{user.id}/events/workouts/{sleep.id}",
            headers=api_key_headers(api_key.id),
        )

        assert response.status_code == 404
        assert db.get(EventRecord, sleep.id) is not None


class TestDeleteSleepSession:
    """Test suite for DELETE /users/{user_id}/events/sleep/{sleep_id}."""

    def test_delete_sleep_success(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        sleep = EventRecordFactory(mapping=ds, category="sleep", type="sleep")
        SleepDetailsFactory(event_record=sleep)
        api_key = ApiKeyFactory()

        response = client.delete(
            f"/api/v1/users/{user.id}/events/sleep/{sleep.id}",
            headers=api_key_headers(api_key.id),
        )

        assert response.status_code == 204
        assert db.get(EventRecord, sleep.id) is None

    def test_delete_sleep_cascades_details(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        sleep = EventRecordFactory(mapping=ds, category="sleep", type="sleep")
        detail = SleepDetailsFactory(event_record=sleep)
        detail_record_id = detail.record_id
        api_key = ApiKeyFactory()

        response = client.delete(
            f"/api/v1/users/{user.id}/events/sleep/{sleep.id}",
            headers=api_key_headers(api_key.id),
        )

        assert response.status_code == 204
        remaining = db.query(EventRecordDetail).filter(EventRecordDetail.record_id == detail_record_id).first()
        assert remaining is None

    def test_delete_sleep_not_found(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        api_key = ApiKeyFactory()

        response = client.delete(
            f"/api/v1/users/{user.id}/events/sleep/{uuid4()}",
            headers=api_key_headers(api_key.id),
        )

        assert response.status_code == 404

    def test_delete_sleep_wrong_user(self, client: TestClient, db: Session) -> None:
        owner = UserFactory()
        other_user = UserFactory()
        ds = DataSourceFactory(user=owner)
        sleep = EventRecordFactory(mapping=ds, category="sleep", type="sleep")
        api_key = ApiKeyFactory()

        response = client.delete(
            f"/api/v1/users/{other_user.id}/events/sleep/{sleep.id}",
            headers=api_key_headers(api_key.id),
        )

        assert response.status_code == 404
        assert db.get(EventRecord, sleep.id) is not None

    def test_delete_sleep_wrong_category(self, client: TestClient, db: Session) -> None:
        """Deleting a workout record via sleep endpoint should return 404."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        workout = EventRecordFactory(mapping=ds, category="workout", type_="running")
        api_key = ApiKeyFactory()

        response = client.delete(
            f"/api/v1/users/{user.id}/events/sleep/{workout.id}",
            headers=api_key_headers(api_key.id),
        )

        assert response.status_code == 404
        assert db.get(EventRecord, workout.id) is not None
