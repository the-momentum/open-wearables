"""Webhook route contract for Withings.

Withings probes the callback URL with HEAD during ``subscribe``; the dedicated
HEAD route must answer 200.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

HEAD_ENDPOINT = "/api/v1/providers/withings/webhooks"
GET_ENDPOINT = "/api/v1/providers/withings/webhooks"


class TestWithingsWebhookHeadProbe:
    """HEAD on the reachability route and GET on the challenge route must return 200.

    FastAPI does not add HEAD to a GET-only route, so the subscribe-time probe
    needs its own route.
    """

    def test_head_returns_200(self, client: TestClient, db: Session) -> None:
        """HEAD request to the withings webhook endpoint must return 200."""
        response = client.head(HEAD_ENDPOINT)
        assert response.status_code == 200, (
            f"Expected 200 for HEAD probe, got {response.status_code}. "
            "Withings subscribe handshake will fail if this is not 200."
        )

    def test_get_returns_200(self, client: TestClient, db: Session) -> None:
        """GET challenge handling remains available on the separate route."""
        response = client.get(GET_ENDPOINT)
        assert response.status_code == 200

    def test_head_returns_empty_body(self, client: TestClient, db: Session) -> None:
        """HEAD response must have no body (HTTP spec requirement)."""
        response = client.head(HEAD_ENDPOINT)
        assert response.content == b""
