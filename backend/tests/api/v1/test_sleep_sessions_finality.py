"""GET /events/sleep says whether each session is final."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.enums import ProviderName
from tests.factories import ApiKeyFactory, DataSourceFactory, EventRecordFactory, SleepDetailsFactory, UserFactory
from tests.utils import api_key_headers


def test_sleep_sessions_say_whether_they_are_final(client: TestClient, db: Session) -> None:
    user = UserFactory()
    night = EventRecordFactory(
        mapping=DataSourceFactory(user=user, provider=ProviderName.APPLE), category="sleep", type_="sleep"
    )
    SleepDetailsFactory(event_record=night)
    api_key = ApiKeyFactory()

    response = client.get(
        f"/api/v1/users/{user.id}/events/sleep",
        params={"start_date": "2020-01-01T00:00:00Z", "end_date": "2030-01-01T00:00:00Z"},
        headers=api_key_headers(api_key.plain_key),
    )

    assert response.status_code == 200
    assert [session["is_final"] for session in response.json()["data"]] == [True]
