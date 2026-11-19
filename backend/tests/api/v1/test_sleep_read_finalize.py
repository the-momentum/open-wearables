"""Sleep read endpoints trigger stale inline sleep finalization."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import ApiKeyFactory, UserFactory
from tests.utils import api_key_headers


def test_sleep_events_get_triggers_stale_finalization(client: TestClient, db: Session) -> None:
    user = UserFactory()
    api_key = ApiKeyFactory()

    with patch("app.api.routes.v1.events.finalize_stale_sleep_for_user", MagicMock(return_value=False)) as finalize:
        response = client.get(
            f"/api/v1/users/{user.id}/events/sleep",
            params={"start_date": "2026-01-01T00:00:00Z", "end_date": "2026-01-08T00:00:00Z"},
            headers=api_key_headers(api_key.id),
        )

    assert response.status_code == 200
    finalize.assert_called_once()
    assert finalize.call_args.args[1] == user.id


def test_sleep_summary_get_triggers_stale_finalization(client: TestClient, db: Session) -> None:
    user = UserFactory()
    api_key = ApiKeyFactory()

    with patch("app.api.routes.v1.summaries.finalize_stale_sleep_for_user", MagicMock(return_value=False)) as finalize:
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/sleep",
            params={"start_date": "2026-01-01T00:00:00Z", "end_date": "2026-01-08T00:00:00Z"},
            headers=api_key_headers(api_key.id),
        )

    assert response.status_code == 200
    finalize.assert_called_once()
    assert finalize.call_args.args[1] == user.id
