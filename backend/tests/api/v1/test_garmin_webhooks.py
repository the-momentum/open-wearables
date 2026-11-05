"""Tests for Garmin webhook HTTP contract layer.

Garmin webhooks are accepted only on the callback URL that carries GARMIN_WEBHOOK_TOKEN:
Garmin does not sign its notifications, and the garmin-client-id header it sends is
public. The endpoint immediately returns {"status": "accepted"} and enqueues all
processing to the process_push Celery task. Processing logic is tested in
tests/tasks/test_garmin_webhook_task.py.
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.config import settings
from app.constants.celery_tasks import CeleryTask
from app.main import api
from app.services.providers.garmin.webhook_handler import check_webhook_token_configured

TOKEN = "3f9c1e7a5b2d4c8e9a0b1c2d3e4f5a6b"
BASE = "/api/v1/providers/garmin/webhooks"
PUSH_ENDPOINT = f"{BASE}/{TOKEN}"
LEGACY_PUSH_ENDPOINT = "/api/v1/garmin/webhooks/push"
LEGACY_PING_ENDPOINT = "/api/v1/garmin/webhooks/ping"
WEBHOOK_HANDLER = "app.services.providers.garmin.webhook_handler"
URL_HINT = f"{BASE}/<GARMIN_WEBHOOK_TOKEN>"

VALID_CLIENT_ID = "test-client-id"
HEADERS = {"garmin-client-id": VALID_CLIENT_ID}


@pytest.fixture(autouse=True)
def _configure_garmin() -> Generator[None, None, None]:
    """Pin the Garmin client id and webhook token so the checks are deterministic."""
    with (
        patch.object(settings, "garmin_client_id", VALID_CLIENT_ID),
        patch.object(settings, "garmin_webhook_token", SecretStr(TOKEN)),
    ):
        yield


@pytest.fixture
def celery() -> Generator[MagicMock, None, None]:
    with patch(f"{WEBHOOK_HANDLER}.celery_app") as mock, patch(f"{WEBHOOK_HANDLER}.store_raw_payload"):
        mock.send_task.return_value.id = "task-1"
        yield mock


class TestGarminWebhookCallbackToken:
    """The token in the callback path is what authenticates a Garmin notification."""

    def test_notification_on_the_token_url_is_accepted(self, client: TestClient, celery: MagicMock) -> None:
        response = client.post(PUSH_ENDPOINT, headers=HEADERS, json={"dailies": [{"userId": "u1"}]})

        assert response.status_code == 200
        assert response.json() == {"status": "accepted"}
        assert celery.send_task.call_args.args[0] == CeleryTask.PROCESS_WEBHOOK_PUSH

    @pytest.mark.parametrize(
        "path",
        [BASE, f"{BASE}/{TOKEN[:-1]}x", f"{BASE}/{TOKEN}x", f"{BASE}/żółw"],
        ids=["no-token", "wrong-token", "longer-token", "non-ascii-token"],
    )
    def test_notification_without_the_right_token_is_rejected(
        self, client: TestClient, celery: MagicMock, path: str
    ) -> None:
        """The public client id header alone is not enough: that is what ENG-1895 exploited."""
        response = client.post(path, headers=HEADERS, json={"deregistrations": [{"userId": "u1"}]})

        assert response.status_code == 401
        celery.send_task.assert_not_called()

    def test_every_notification_is_rejected_while_the_token_is_unset(
        self, client: TestClient, celery: MagicMock
    ) -> None:
        with patch.object(settings, "garmin_webhook_token", None):
            responses = [
                client.post(path, headers=HEADERS, json={"dailies": []})
                for path in (BASE, PUSH_ENDPOINT, LEGACY_PUSH_ENDPOINT)
            ]

        assert [r.status_code for r in responses] == [401, 401, 401]
        celery.send_task.assert_not_called()

    def test_token_is_checked_before_the_body(self, client: TestClient) -> None:
        response = client.post(BASE, content=b"not json", headers={**HEADERS, "Content-Type": "application/json"})
        assert response.status_code == 401


class TestGarminWebhookClientIdHeader:
    """With the right token, the garmin-client-id header still filters out noise."""

    def test_missing_client_id_returns_401(self, client: TestClient, db: Session) -> None:
        response = client.post(PUSH_ENDPOINT, json={"activities": []})
        assert response.status_code == 401

    def test_wrong_client_id_returns_401(self, client: TestClient, db: Session) -> None:
        response = client.post(
            PUSH_ENDPOINT,
            headers={"garmin-client-id": "attacker-invented"},
            json={"activities": []},
        )
        assert response.status_code == 401

    def test_rejection_log_hides_the_token(self, client: TestClient, db: Session) -> None:
        with patch("app.services.providers.templates.base_webhook_handler.logger") as logger:
            response = client.post(PUSH_ENDPOINT, headers={"garmin-client-id": "attacker-invented"}, json={})

        assert response.status_code == 401
        assert logger.warning.call_args.kwargs["path"] == f"{BASE}/redacted"
        assert TOKEN not in str(logger.mock_calls)

    def test_unconfigured_client_id_rejects_any_request(self, client: TestClient, db: Session) -> None:
        with patch.object(settings, "garmin_client_id", None):
            response = client.post(PUSH_ENDPOINT, headers=HEADERS, json={"activities": []})
        assert response.status_code == 401

    def test_valid_request_returns_accepted(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        response = client.post(PUSH_ENDPOINT, headers=HEADERS, json={"activities": []})

        assert response.status_code == 200
        assert response.json() == {"status": "accepted"}

    def test_invalid_json_returns_400(self, client: TestClient, db: Session) -> None:
        response = client.post(
            PUSH_ENDPOINT,
            content=b"not json",
            headers={**HEADERS, "Content-Type": "application/json"},
        )
        assert response.status_code == 400


class TestGarminWebhookTaskEnqueue:
    """Verify that dispatch() enqueues the process_push Celery task."""

    def test_enqueues_process_push_task(
        self,
        client: TestClient,
        db: Session,
    ) -> None:
        """POST enqueues process_push with the raw payload."""
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_123",
                    "activityId": 12345,
                    "activityType": "RUNNING",
                    "startTimeInSeconds": 1763597760,
                    "durationInSeconds": 3600,
                },
            ],
        }

        with patch(f"{WEBHOOK_HANDLER}.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="test-task-id")
            response = client.post(PUSH_ENDPOINT, headers=HEADERS, json=payload)

        assert response.status_code == 200
        assert response.json() == {"status": "accepted"}
        mock_celery.send_task.assert_called_once()
        task_name, _ = mock_celery.send_task.call_args[0][0], mock_celery.send_task.call_args
        assert task_name == CeleryTask.PROCESS_WEBHOOK_PUSH

    def test_enqueues_task_with_correct_payload(
        self,
        client: TestClient,
        db: Session,
    ) -> None:
        """The payload passed to send_task matches the incoming webhook body."""
        payload = {"hrv": [{"userId": "u1", "summaryId": "s1"}]}

        with patch(f"{WEBHOOK_HANDLER}.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="task-xyz")
            client.post(PUSH_ENDPOINT, headers=HEADERS, json=payload)

        # send_task(CeleryTask.PROCESS_WEBHOOK_PUSH, args=["garmin", payload, trace_id])
        sent_args = mock_celery.send_task.call_args[1]["args"]
        assert sent_args[0] == "garmin"
        assert sent_args[1] == payload


class TestGarminWebhookRouting:
    """Routing and method checks for the unified provider webhook router."""

    def test_get_challenge_returns_501(self, client: TestClient, db: Session) -> None:
        """Garmin does not support GET subscription challenges — expect 501 once authenticated."""
        assert client.get(BASE).status_code == 401
        assert client.get(PUSH_ENDPOINT).status_code == 501

    def test_head_probe_returns_501(self, client: TestClient, db: Session) -> None:
        assert client.head(BASE).status_code == 401
        assert client.head(PUSH_ENDPOINT).status_code == 501

    def test_unknown_provider_is_a_validation_error(self, client: TestClient, db: Session) -> None:
        """Unknown provider names return 422."""
        response = client.post(
            "/api/v1/providers/unknown_provider/webhooks",
            headers={"garmin-client-id": "x"},
            json={},
        )
        assert response.status_code == 422


class TestGarminDeprecatedRoutes:
    """Legacy /garmin/webhooks/* routes cannot carry the token, so they always answer 401."""

    @pytest.mark.parametrize("path", [LEGACY_PUSH_ENDPOINT, LEGACY_PING_ENDPOINT])
    def test_legacy_route_is_rejected(self, client: TestClient, celery: MagicMock, path: str) -> None:
        with patch(f"{WEBHOOK_HANDLER}.logger") as logger:
            response = client.post(path, headers=HEADERS, json={"dailies": [{"userId": "u1"}]})

        assert response.status_code == 401
        assert URL_HINT in response.json()["detail"]
        celery.send_task.assert_not_called()
        logger.error.assert_called_once()
        assert logger.error.call_args.kwargs["webhook_url"].endswith(URL_HINT)
        assert TOKEN not in str(logger.error.call_args)

    def test_legacy_route_without_our_client_id_logs_only_a_warning(
        self, client: TestClient, celery: MagicMock
    ) -> None:
        """A scanner hitting the old path is no reason to page anyone."""
        with (
            patch(f"{WEBHOOK_HANDLER}.logger") as handler_logger,
            patch("app.api.routes.v1.deprecated_webhooks.logger") as route_logger,
        ):
            response = client.post(LEGACY_PUSH_ENDPOINT, json={})

        assert response.status_code == 401
        handler_logger.error.assert_not_called()
        route_logger.warning.assert_called_once()


class TestGarminRejectedUrlReport:
    """Garmin itself turned away on the unified route is an error with the URL to set."""

    @pytest.mark.parametrize(
        "path",
        [BASE, f"{BASE}/{TOKEN[:-1]}x"],
        ids=["tokenless-canonical-url", "stale-token"],
    )
    def test_our_garmin_app_without_the_token_is_an_error(
        self, client: TestClient, celery: MagicMock, path: str
    ) -> None:
        with patch(f"{WEBHOOK_HANDLER}.logger") as logger:
            response = client.post(path, headers=HEADERS, json={"dailies": []})

        assert response.status_code == 401
        logger.error.assert_called_once()
        assert logger.error.call_args.kwargs["webhook_url"].endswith(URL_HINT)
        assert logger.error.call_args.kwargs["path"] in (BASE, f"{BASE}/redacted")
        assert TOKEN[:-1] not in str(logger.error.call_args)

    def test_unset_token_is_an_error_for_our_garmin_app(self, client: TestClient, celery: MagicMock) -> None:
        with patch.object(settings, "garmin_webhook_token", None), patch(f"{WEBHOOK_HANDLER}.logger") as logger:
            response = client.post(PUSH_ENDPOINT, headers=HEADERS, json={"dailies": []})

        assert response.status_code == 401
        logger.error.assert_called_once()

    @pytest.mark.parametrize("headers", [{}, {"garmin-client-id": "attacker-invented"}], ids=["none", "other"])
    def test_other_callers_are_not_an_error(
        self, client: TestClient, celery: MagicMock, headers: dict[str, str]
    ) -> None:
        with patch(f"{WEBHOOK_HANDLER}.logger") as logger:
            response = client.post(BASE, headers=headers, json={})

        assert response.status_code == 401
        logger.error.assert_not_called()


class TestStartupCheck:
    """Garmin delivers everything by push, so a missing token stops all Garmin data."""

    @pytest.mark.parametrize("token", [None, SecretStr("")], ids=["unset", "empty-as-in-env-example"])
    def test_missing_token_is_a_warning_when_garmin_credentials_are_set(self, token: SecretStr | None) -> None:
        """Only a warning: .env.example ships placeholder Garmin credentials."""
        with (
            patch.object(settings, "garmin_client_secret", SecretStr("client-secret")),
            patch.object(settings, "garmin_webhook_token", token),
            patch(f"{WEBHOOK_HANDLER}.logger") as logger,
        ):
            check_webhook_token_configured()

        logger.warning.assert_called_once()
        logger.error.assert_not_called()
        assert "GARMIN_WEBHOOK_TOKEN is not set" in logger.warning.call_args.args[0]
        assert "alert" not in logger.warning.call_args.kwargs

    @pytest.mark.parametrize(
        ("client_secret", "token"),
        [(SecretStr("client-secret"), SecretStr(TOKEN)), (None, None), (SecretStr(""), None)],
        ids=["token-set", "garmin-not-configured", "empty-client-secret"],
    )
    def test_nothing_is_logged_otherwise(self, client_secret: SecretStr | None, token: SecretStr | None) -> None:
        with (
            patch.object(settings, "garmin_client_secret", client_secret),
            patch.object(settings, "garmin_webhook_token", token),
            patch(f"{WEBHOOK_HANDLER}.logger") as logger,
        ):
            check_webhook_token_configured()

        logger.warning.assert_not_called()

    def test_runs_at_application_startup(self) -> None:
        with patch("app.main.check_garmin_webhook_token_configured") as check, TestClient(api):
            pass

        check.assert_called_once()
