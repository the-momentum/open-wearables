"""
Tests for the event totals endpoints, which add up what the lists page through:

- GET /api/v1/users/{user_id}/events/workouts/totals
- GET /api/v1/users/{user_id}/events/sleep/totals
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.enums import ProviderName
from tests.factories import (
    ApiKeyFactory,
    DataSourceFactory,
    EventRecordFactory,
    SleepDetailsFactory,
    UserFactory,
    WorkoutDetailsFactory,
)
from tests.utils import api_key_headers


def _get(client: TestClient, path: str, **extra: object) -> dict | list:
    now = datetime.now(timezone.utc)
    response = client.get(
        path,
        headers=api_key_headers(ApiKeyFactory().plain_key),
        params={
            "start_date": (now - timedelta(days=30)).isoformat(),
            "end_date": (now + timedelta(days=1)).isoformat(),
            **extra,
        },
    )
    assert response.status_code == 200
    return response.json()


def _listed(client: TestClient, user_id: object, kind: str) -> list:
    return _get(client, f"/api/v1/users/{user_id}/events/{kind}", limit=100)["data"]


class TestWorkoutTotals:
    """GET /users/{user_id}/events/workouts/totals adds up what the list would page through."""

    def _totals(self, client: TestClient, user_id: object, **extra: object) -> dict:
        return _get(client, f"/api/v1/users/{user_id}/events/workouts/totals", **extra)

    def test_adds_up_the_workouts_the_list_returns(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        garmin = DataSourceFactory(user=user, provider=ProviderName.GARMIN)
        oura = DataSourceFactory(user=user, provider=ProviderName.OURA)
        for ds, kind, kcal, meters in (
            (garmin, "running", "500.5", "10000"),
            (garmin, "cycling", "800", None),
            (oura, "running", None, "5000"),
        ):
            workout = EventRecordFactory(mapping=ds, category="workout", type_=kind, duration_seconds=1800)
            WorkoutDetailsFactory(
                event_record=workout,
                energy_burned=Decimal(kcal) if kcal else None,
                distance=Decimal(meters) if meters else None,
            )
        # Not a workout, and another user's: neither counts.
        EventRecordFactory(mapping=garmin, category="sleep", duration_seconds=28800)
        EventRecordFactory(mapping=DataSourceFactory(), category="workout", duration_seconds=999)

        assert self._totals(client, user.id) == {
            "count": 3,
            "duration_seconds": 5400,
            "calories_kcal": 1300.5,
            "distance_meters": 15000.0,
        }
        # The list's own filters narrow it the same way.
        assert self._totals(client, user.id, provider="oura")["count"] == 1
        assert self._totals(client, user.id, type="cycling")["distance_meters"] is None
        assert self._totals(client, user.id)["count"] == len(_listed(client, user.id, "workouts"))

    def test_is_zero_with_nothing_to_add(self, client: TestClient, db: Session) -> None:
        assert self._totals(client, UserFactory().id) == {
            "count": 0,
            "duration_seconds": 0,
            "calories_kcal": None,
            "distance_meters": None,
        }


class TestSleepTotals:
    """GET /users/{user_id}/events/sleep/totals adds up the sessions the sleep list returns."""

    def _totals(self, client: TestClient, user_id: object, **extra: object) -> dict:
        return _get(client, f"/api/v1/users/{user_id}/events/sleep/totals", **extra)

    def test_adds_up_nights_and_naps_as_the_list_reads_them(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.OURA)
        night = EventRecordFactory(mapping=ds, category="sleep", type_="sleep", duration_seconds=30000)
        SleepDetailsFactory(
            event_record=night,
            sleep_total_duration_minutes=420,
            sleep_time_in_bed_minutes=470,
            sleep_efficiency_score=Decimal("90"),
        )
        # No time in bed reported: its span stands in, as the list's fallback does.
        nap = EventRecordFactory(mapping=ds, category="sleep", type_="sleep", duration_seconds=1800)
        SleepDetailsFactory(
            event_record=nap,
            sleep_total_duration_minutes=25,
            sleep_time_in_bed_minutes=None,
            sleep_efficiency_score=Decimal("80"),
            is_nap=True,
        )
        EventRecordFactory(mapping=ds, category="workout", duration_seconds=3600)

        assert self._totals(client, user.id) == {
            "count": 2,
            "naps": 1,
            "sleep_duration_seconds": (420 + 25) * 60,
            "time_in_bed_seconds": 470 * 60 + 1800,
            "avg_efficiency_percent": 85.0,
        }
        assert self._totals(client, user.id, is_nap="true")["count"] == 1
        assert self._totals(client, user.id, is_nap="false")["naps"] == 0
        assert self._totals(client, user.id)["count"] == len(_listed(client, user.id, "sleep"))

    def test_is_zero_with_nothing_to_add(self, client: TestClient, db: Session) -> None:
        assert self._totals(client, UserFactory().id) == {
            "count": 0,
            "naps": 0,
            "sleep_duration_seconds": 0,
            "time_in_bed_seconds": 0,
            "avg_efficiency_percent": None,
        }
