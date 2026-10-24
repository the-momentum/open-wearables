"""Tests for the endpoints a user's own app calls with their SDK token."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User, UserConnection
from app.schemas.auth import ConnectionStatus
from app.services.sdk_token_service import create_sdk_user_token
from tests.factories import (
    ApiKeyFactory,
    DataPointSeriesFactory,
    DataSourceFactory,
    DeveloperFactory,
    EventRecordFactory,
    SeriesTypeDefinitionFactory,
    UserConnectionFactory,
    UserFactory,
)
from tests.utils import api_key_headers, developer_auth_headers

TODAY = date(2026, 10, 24)


def sdk_headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_sdk_user_token('app', str(user_id))}"}


def at(day: date, hour: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)


class TestOverview:
    def _seed_week(self, user: User) -> None:
        source = DataSourceFactory(user=user)
        steps = SeriesTypeDefinitionFactory.get_or_create_steps()
        rhr = SeriesTypeDefinitionFactory.get_or_create_resting_heart_rate()
        # 6000 steps on each of the 3 days before, 9000 today.
        for offset, value in ((3, 6000), (2, 6000), (1, 6000), (0, 9000)):
            day = TODAY - timedelta(days=offset)
            DataPointSeriesFactory(mapping=source, series_type=steps, value=Decimal(value), recorded_at=at(day, 12))
            DataPointSeriesFactory(mapping=source, series_type=rhr, value=Decimal(60 + offset), recorded_at=at(day, 7))
        # Last night: 7 hours.
        EventRecordFactory(
            mapping=source,
            category="sleep",
            type="sleep",
            start_datetime=at(TODAY - timedelta(days=1), 23),
            end_datetime=at(TODAY, 6),
            duration_seconds=7 * 3600,
        )

    def test_tiles_compare_today_with_the_days_before(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        self._seed_week(user)

        response = client.get(
            f"/api/v1/sdk/users/{user.id}/overview",
            params={"today": TODAY.isoformat(), "days": 7},
            headers=sdk_headers(user.id),
        )

        assert response.status_code == 200, response.text
        body = response.json()
        tiles = {tile["metric"]: tile for tile in body["tiles"]}
        assert tiles["steps"]["today"] == 9000
        assert tiles["steps"]["average"] == 6000
        assert tiles["steps"]["delta_percent"] == 50.0
        assert tiles["resting_heart_rate"]["today"] == 60
        assert tiles["sleep_minutes"]["today"] == 420
        assert tiles["sleep_minutes"]["average"] is None

    def test_series_have_one_point_per_day_ending_today(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        self._seed_week(user)

        body = client.get(
            f"/api/v1/sdk/users/{user.id}/overview",
            params={"today": TODAY.isoformat(), "days": 7},
            headers=sdk_headers(user.id),
        ).json()

        steps = body["series"]["steps"]
        assert [point["date"] for point in steps][-1] == TODAY.isoformat()
        assert len(steps) == 7
        assert steps[0]["value"] is None
        assert steps[-1]["value"] == 9000
        assert set(body["series"]) == {"steps", "sleep_minutes", "resting_heart_rate"}

    def test_metrics_without_data_have_no_tile(self, client: TestClient, db: Session) -> None:
        user = UserFactory()

        body = client.get(
            f"/api/v1/sdk/users/{user.id}/overview",
            params={"today": TODAY.isoformat()},
            headers=sdk_headers(user.id),
        ).json()

        assert body["tiles"] == []

    def test_sdk_token_reads_only_its_own_user(self, client: TestClient, db: Session) -> None:
        user, other = UserFactory(), UserFactory()

        response = client.get(f"/api/v1/sdk/users/{other.id}/overview", headers=sdk_headers(user.id))

        assert response.status_code == 403

    def test_api_key_may_read_any_user(self, client: TestClient, db: Session) -> None:
        user = UserFactory()

        response = client.get(
            f"/api/v1/sdk/users/{user.id}/overview", headers=api_key_headers(ApiKeyFactory().plain_key)
        )

        assert response.status_code == 200

    def test_requires_auth(self, client: TestClient, db: Session) -> None:
        assert client.get(f"/api/v1/sdk/users/{UserFactory().id}/overview").status_code == 401


class TestOwnConnections:
    def test_lists_own_connections_without_tokens(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE, access_token="secret")

        response = client.get(f"/api/v1/sdk/users/{user.id}/connections", headers=sdk_headers(user.id))

        assert response.status_code == 200
        assert [c["provider"] for c in response.json()] == ["garmin"]
        assert "secret" not in response.text

    def test_cannot_list_another_user(self, client: TestClient, db: Session) -> None:
        response = client.get(
            f"/api/v1/sdk/users/{UserFactory().id}/connections", headers=sdk_headers(UserFactory().id)
        )

        assert response.status_code == 403

    def test_user_disconnects_own_cloud_account(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="garmin",
            status=ConnectionStatus.ACTIVE,
            access_token="secret",
            refresh_token="refresh",
        )

        with patch("app.services.user_connection_service.UserConnectionService.deregister_from_provider"):
            response = client.delete(f"/api/v1/sdk/users/{user.id}/connections/garmin", headers=sdk_headers(user.id))

        assert response.status_code == 204
        connection = db.query(UserConnection).filter_by(user_id=user.id, provider="garmin").one()
        assert connection.status != ConnectionStatus.ACTIVE
        assert connection.access_token is None

    def test_cannot_disconnect_another_user(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)

        response = client.delete(
            f"/api/v1/sdk/users/{user.id}/connections/garmin", headers=sdk_headers(UserFactory().id)
        )

        assert response.status_code == 403


class TestDataDeletionRequest:
    def test_emails_the_organisation_once_a_day(self, client: TestClient, db: Session) -> None:
        user = UserFactory(first_name="Ada", last_name="Lovelace")
        client.patch(
            "/api/v1/instance/settings",
            json={"support_email": "help@acmehealth.com"},
            headers=_developer_headers(),
        )

        with patch(
            "app.services.data_deletion_request_service.send_data_deletion_request_email", return_value=True
        ) as send:
            first = client.post(f"/api/v1/sdk/users/{user.id}/data-deletion-request", headers=sdk_headers(user.id))
            second = client.post(f"/api/v1/sdk/users/{user.id}/data-deletion-request", headers=sdk_headers(user.id))

        assert first.status_code == 202
        assert first.json() == {"notified": True}
        assert second.json() == {"notified": False}
        send.assert_called_once()
        to, label, url = send.call_args.args
        assert to == "help@acmehealth.com"
        assert "Ada Lovelace" in label
        assert url.endswith(f"/users/{user.id}")

    def test_falls_back_to_developers(self, client: TestClient, db: Session) -> None:
        DeveloperFactory(email="dev@acmehealth.com")
        user = UserFactory()

        with patch(
            "app.services.data_deletion_request_service.send_data_deletion_request_email", return_value=True
        ) as send:
            client.post(f"/api/v1/sdk/users/{user.id}/data-deletion-request", headers=sdk_headers(user.id))

        assert send.call_args.args[0] == "dev@acmehealth.com"

    def test_email_failure_is_reported_and_can_be_retried(self, client: TestClient, db: Session) -> None:
        DeveloperFactory(email="dev@acmehealth.com")
        user = UserFactory()
        url = f"/api/v1/sdk/users/{user.id}/data-deletion-request"

        with patch("app.services.data_deletion_request_service.send_data_deletion_request_email", return_value=False):
            failed = client.post(url, headers=sdk_headers(user.id))
        with patch("app.services.data_deletion_request_service.send_data_deletion_request_email", return_value=True):
            retried = client.post(url, headers=sdk_headers(user.id))

        assert failed.status_code == 503
        assert retried.json() == {"notified": True}

    def test_only_for_own_user(self, client: TestClient, db: Session) -> None:
        response = client.post(
            f"/api/v1/sdk/users/{UserFactory().id}/data-deletion-request", headers=sdk_headers(UserFactory().id)
        )

        assert response.status_code == 403


def _developer_headers() -> dict[str, str]:
    return developer_auth_headers(DeveloperFactory().id)
