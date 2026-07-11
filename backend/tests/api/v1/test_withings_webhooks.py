"""Authenticated webhook route contract for Withings.

Withings probes the callback URL with HEAD during ``subscribe``; the dedicated
HEAD route must answer 200.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.config import settings

CALLBACK_TOKEN = "withings-test-token"
ENDPOINT = "/api/v1/providers/withings/webhooks"


class TestWithingsWebhookHeadProbe:
    """HEAD on the reachability route and GET on the challenge route must return 200.

    FastAPI does not add HEAD to a GET-only route, so the subscribe-time probe
    needs its own route.
    """

    def test_head_returns_200(self, client: TestClient, db: Session) -> None:
        """HEAD request to the withings webhook endpoint must return 200."""
        with patch.object(settings, "withings_webhook_token", SecretStr(CALLBACK_TOKEN)):
            response = client.head(ENDPOINT, params={"token": CALLBACK_TOKEN})
        assert response.status_code == 200, (
            f"Expected 200 for HEAD probe, got {response.status_code}. "
            "Withings subscribe handshake will fail if this is not 200."
        )

    def test_get_returns_200(self, client: TestClient, db: Session) -> None:
        """GET challenge handling remains available on the separate route."""
        with patch.object(settings, "withings_webhook_token", SecretStr(CALLBACK_TOKEN)):
            response = client.get(ENDPOINT, params={"token": CALLBACK_TOKEN})
        assert response.status_code == 200

    def test_head_returns_empty_body(self, client: TestClient, db: Session) -> None:
        """HEAD response must have no body (HTTP spec requirement)."""
        with patch.object(settings, "withings_webhook_token", SecretStr(CALLBACK_TOKEN)):
            response = client.head(ENDPOINT, params={"token": CALLBACK_TOKEN})
        assert response.content == b""

    def test_head_rejects_invalid_token(self, client: TestClient, db: Session) -> None:
        with patch.object(settings, "withings_webhook_token", SecretStr(CALLBACK_TOKEN)):
            response = client.head(ENDPOINT, params={"token": "wrong-token"})
        assert response.status_code == 401


class TestWithingsWebhookNotification:
    def test_post_rejects_missing_token(self, client: TestClient, db: Session) -> None:
        with patch.object(settings, "withings_webhook_token", SecretStr(CALLBACK_TOKEN)):
            response = client.post(ENDPOINT, content=b"userid=123&appli=1&startdate=1&enddate=2")
        assert response.status_code == 401
