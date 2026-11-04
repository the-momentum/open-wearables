"""GET /events/sleep says whether each session is final."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.enums import ProviderName
from tests.factories import ApiKeyFactory, DataSourceFactory, EventRecordFactory, SleepDetailsFactory, UserFactory
from tests.utils import api_key_headers


def test_sleep_sessions_say_whether_they_are_final(client: TestClient, db: Session) -> None:
    user = UserFactory()
    watch = DataSourceFactory(user=user, provider=ProviderName.GARMIN, source="garmin")
    end = datetime.now(timezone.utc) - timedelta(hours=1)
    last_night, night_before = (
        EventRecordFactory(
            mapping=watch,
            category="sleep",
            type_="sleep",
            start_datetime=end - timedelta(hours=8, days=days),
            end_datetime=end - timedelta(days=days),
        )
        for days in (0, 1)
    )
    SleepDetailsFactory(event_record=last_night, provider_state="AUTO_TENTATIVE")
    SleepDetailsFactory(event_record=night_before, provider_state="ENHANCED_FINAL")
    api_key = ApiKeyFactory()

    response = client.get(
        f"/api/v1/users/{user.id}/events/sleep",
        params={"start_date": "2020-01-01T00:00:00Z", "end_date": "2030-01-01T00:00:00Z"},
        headers=api_key_headers(api_key.plain_key),
    )

    assert response.status_code == 200
    assert {session["id"]: session["is_final"] for session in response.json()["data"]} == {
        str(last_night.id): False,
        str(night_before.id): True,
    }
