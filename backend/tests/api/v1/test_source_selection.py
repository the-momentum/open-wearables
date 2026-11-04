from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.enums import SourceSelection
from app.services import timeseries_service
from app.services.event_record_service import event_record_service
from tests.factories import ApiKeyFactory, UserFactory
from tests.utils import api_key_headers

RANGE = {"start_time": "2026-04-01T00:00:00Z", "end_time": "2026-04-02T00:00:00Z"}
DATES = {"start_date": "2026-04-01T00:00:00Z", "end_date": "2026-04-02T00:00:00Z"}


def _selection(spy: MagicMock) -> SourceSelection:
    return spy.call_args.kwargs["source_selection"]


class TestTimeseriesSourceSelection:
    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ({}, SourceSelection.ALL),
            ({"filter_by_priority": "true"}, SourceSelection.PER_RANGE),
            ({"filter_by_priority": "true", "source_selection": "all"}, SourceSelection.ALL),
            ({"source_selection": "per_period", "resolution": "1day"}, SourceSelection.PER_PERIOD),
        ],
    )
    def test_selection_reaches_the_service(
        self, client: TestClient, db: Session, query: dict, expected: SourceSelection
    ) -> None:
        user = UserFactory()
        with patch.object(timeseries_service, "get_timeseries", wraps=timeseries_service.get_timeseries) as spy:
            response = client.get(
                f"/api/v1/users/{user.id}/timeseries",
                params={**RANGE, "types": "steps", **query},
                headers=api_key_headers(ApiKeyFactory().plain_key),
            )

        assert response.status_code == 200, response.text
        assert _selection(spy) == expected

    def test_per_period_needs_a_resolution(self, client: TestClient, db: Session) -> None:
        response = client.get(
            f"/api/v1/users/{UserFactory().id}/timeseries",
            params={**RANGE, "types": "steps", "source_selection": "per_period"},
            headers=api_key_headers(ApiKeyFactory().plain_key),
        )

        assert response.status_code == 400


class TestEventSourceSelection:
    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ({}, SourceSelection.ALL),
            ({"filter_by_priority": "true"}, SourceSelection.PER_SESSION),
            ({"filter_by_priority": "true", "source_selection": "all"}, SourceSelection.ALL),
        ],
    )
    def test_sleep_selection_reaches_the_service(
        self, client: TestClient, db: Session, query: dict, expected: SourceSelection
    ) -> None:
        user = UserFactory()
        with patch.object(
            event_record_service, "get_sleep_sessions", wraps=event_record_service.get_sleep_sessions
        ) as spy:
            response = client.get(
                f"/api/v1/users/{user.id}/events/sleep",
                params={**DATES, **query},
                headers=api_key_headers(ApiKeyFactory().plain_key),
            )

        assert response.status_code == 200, response.text
        assert _selection(spy) == expected

    def test_workouts_accept_per_session(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        with patch.object(event_record_service, "get_workouts", wraps=event_record_service.get_workouts) as spy:
            response = client.get(
                f"/api/v1/users/{user.id}/events/workouts",
                params={**DATES, "source_selection": "per_session"},
                headers=api_key_headers(ApiKeyFactory().plain_key),
            )

        assert response.status_code == 200, response.text
        assert _selection(spy) == SourceSelection.PER_SESSION
