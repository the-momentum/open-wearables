"""GET and DELETE /api/v1/users/{user_id}/events/reproductive-health."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import EventRecord, ReproductiveHealthDetails
from tests.factories import (
    ApiKeyFactory,
    DataSourceFactory,
    EventRecordFactory,
    ReproductiveHealthDetailsFactory,
    UserFactory,
)
from tests.utils import api_key_headers

DAY = datetime(2026, 11, 1, tzinfo=timezone.utc)
RANGE = {"start_date": "2026-10-01T00:00:00Z", "end_date": "2026-12-01T00:00:00Z"}


def _entry(
    data_source: object,
    entry_type: str,
    start: datetime = DAY,
    end: datetime | None = None,
    **detail: object,
) -> EventRecord:
    record = EventRecordFactory(
        mapping=data_source,
        category="reproductive_health",
        type_=entry_type,
        start_datetime=start,
        end_datetime=end or start + timedelta(days=1),
        duration_seconds=None,
    )
    ReproductiveHealthDetailsFactory(event_record=record, **detail)
    return record


class TestListReproductiveHealth:
    def test_lists_entries_with_their_details(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider="apple")
        _entry(ds, "menstrual_flow", value="heavy", cycle_start=True)
        _entry(ds, "sexual_activity", value=None, protection_used=False)
        api_key = ApiKeyFactory()

        response = client.get(
            f"/api/v1/users/{user.id}/events/reproductive-health",
            params=RANGE,
            headers=api_key_headers(api_key.plain_key),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["pagination"]["total_count"] == 2
        by_type = {entry["type"]: entry for entry in body["data"]}
        assert by_type["menstrual_flow"]["value"] == "heavy"
        assert by_type["menstrual_flow"]["cycle_start"] is True
        assert by_type["sexual_activity"]["value"] is None
        assert by_type["sexual_activity"]["protection_used"] is False
        assert by_type["menstrual_flow"]["source"]["provider"] == "apple"

    def test_filters_by_type(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        _entry(ds, "menstrual_flow")
        _entry(ds, "ovulation_test", value="negative")
        api_key = ApiKeyFactory()

        response = client.get(
            f"/api/v1/users/{user.id}/events/reproductive-health",
            params={**RANGE, "type": "ovulation_test"},
            headers=api_key_headers(api_key.plain_key),
        )

        assert response.status_code == 200
        assert [entry["type"] for entry in response.json()["data"]] == ["ovulation_test"]

    def test_unknown_type_is_rejected(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        api_key = ApiKeyFactory()

        response = client.get(
            f"/api/v1/users/{user.id}/events/reproductive-health",
            params={**RANGE, "type": "mood"},
            headers=api_key_headers(api_key.plain_key),
        )

        assert response.status_code == 422

    def test_pages_through_entries(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        for day in range(3):
            _entry(ds, "menstrual_flow", start=DAY + timedelta(days=day))
        api_key = ApiKeyFactory()
        url = f"/api/v1/users/{user.id}/events/reproductive-health"

        first = client.get(url, params={**RANGE, "limit": 2}, headers=api_key_headers(api_key.plain_key)).json()
        second = client.get(
            url,
            params={**RANGE, "limit": 2, "cursor": first["pagination"]["next_cursor"]},
            headers=api_key_headers(api_key.plain_key),
        ).json()

        assert len(first["data"]) == 2
        assert first["pagination"]["has_more"] is True
        assert len(second["data"]) == 1
        assert {e["id"] for e in first["data"]}.isdisjoint({e["id"] for e in second["data"]})

    def test_entries_spanning_the_range_edges_are_listed(self, client: TestClient, db: Session) -> None:
        """A month at a time still returns a period across the month boundary and an ongoing pregnancy."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        november = datetime(2026, 11, 1, tzinfo=timezone.utc)
        _entry(ds, "menstrual_period", start=november - timedelta(days=2), end=november + timedelta(days=2))
        _entry(ds, "pregnancy", start=november + timedelta(days=10), end=november + timedelta(days=250))
        _entry(ds, "menstrual_flow", start=november - timedelta(days=20))
        api_key = ApiKeyFactory()
        url = f"/api/v1/users/{user.id}/events/reproductive-health"

        def listed(start: str, end: str) -> set[str]:
            response = client.get(
                url, params={"start_date": start, "end_date": end}, headers=api_key_headers(api_key.plain_key)
            )
            return {entry["type"] for entry in response.json()["data"]}

        assert listed("2026-10-01T00:00:00Z", "2026-11-01T00:00:00Z") == {"menstrual_period", "menstrual_flow"}
        assert listed("2026-11-01T00:00:00Z", "2026-12-01T00:00:00Z") == {"menstrual_period", "pregnancy"}

    def test_an_entry_at_the_start_of_the_range_is_listed(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        _entry(DataSourceFactory(user=user), "sexual_activity", start=DAY, end=DAY)
        api_key = ApiKeyFactory()

        response = client.get(
            f"/api/v1/users/{user.id}/events/reproductive-health",
            params={"start_date": "2026-11-01T00:00:00Z", "end_date": "2026-11-02T00:00:00Z"},
            headers=api_key_headers(api_key.plain_key),
        )

        assert [entry["type"] for entry in response.json()["data"]] == ["sexual_activity"]

    def test_other_categories_are_not_listed(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        EventRecordFactory(mapping=ds, category="workout", start_datetime=DAY)
        api_key = ApiKeyFactory()

        response = client.get(
            f"/api/v1/users/{user.id}/events/reproductive-health",
            params=RANGE,
            headers=api_key_headers(api_key.plain_key),
        )

        assert response.json()["data"] == []


class TestDeleteReproductiveHealth:
    def test_delete_cascades_details(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        record = _entry(DataSourceFactory(user=user), "pregnancy_test", value="positive")
        api_key = ApiKeyFactory()

        response = client.delete(
            f"/api/v1/users/{user.id}/events/reproductive-health/{record.id}",
            headers=api_key_headers(api_key.plain_key),
        )

        assert response.status_code == 204
        assert db.get(EventRecord, record.id) is None
        assert db.get(ReproductiveHealthDetails, record.id) is None

    def test_another_users_entry_is_not_found(self, client: TestClient, db: Session) -> None:
        record = _entry(DataSourceFactory(user=UserFactory()), "lactation", value=None)
        api_key = ApiKeyFactory()

        response = client.delete(
            f"/api/v1/users/{UserFactory().id}/events/reproductive-health/{record.id}",
            headers=api_key_headers(api_key.plain_key),
        )

        assert response.status_code == 404
        assert db.get(EventRecord, record.id) is not None

    def test_other_category_is_not_found(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        workout = EventRecordFactory(mapping=DataSourceFactory(user=user), category="workout")
        api_key = ApiKeyFactory()

        for record_id in (workout.id, uuid4()):
            response = client.delete(
                f"/api/v1/users/{user.id}/events/reproductive-health/{record_id}",
                headers=api_key_headers(api_key.plain_key),
            )
            assert response.status_code == 404
        assert db.get(EventRecord, workout.id) is not None
