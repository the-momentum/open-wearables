"""GET subscription challenge on the unified provider webhook router."""

from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.config import settings

VERIFY_TOKEN = "strava-verify-token"
CALLBACK_TOKEN = "3f9c1e7a5b2d4c8e9a0b1c2d3e4f5a6b"


def test_provider_without_a_challenge_gets_501(client: TestClient, db: Session) -> None:
    response = client.get("/api/v1/providers/garmin/webhooks")

    assert response.status_code == 501
    assert response.json()["detail"] == "Provider 'garmin' does not support webhook subscription verification via GET."


def test_provider_with_a_challenge_echoes_it(client: TestClient, db: Session) -> None:
    with (
        patch.object(settings, "strava_webhook_verify_token", SecretStr(VERIFY_TOKEN)),
        patch.object(settings, "strava_webhook_token", SecretStr(CALLBACK_TOKEN)),
    ):
        response = client.get(
            f"/api/v1/providers/strava/webhooks/{CALLBACK_TOKEN}",
            params={"hub.mode": "subscribe", "hub.challenge": "abc123", "hub.verify_token": VERIFY_TOKEN},
        )

    assert response.status_code == 200
    assert response.json() == {"hub.challenge": "abc123"}


def test_challenge_with_a_wrong_token_is_rejected(client: TestClient, db: Session) -> None:
    with (
        patch.object(settings, "strava_webhook_verify_token", SecretStr(VERIFY_TOKEN)),
        patch.object(settings, "strava_webhook_token", SecretStr(CALLBACK_TOKEN)),
    ):
        response = client.get(
            f"/api/v1/providers/strava/webhooks/{CALLBACK_TOKEN}",
            params={"hub.mode": "subscribe", "hub.challenge": "abc123", "hub.verify_token": "guess"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid verify token"
