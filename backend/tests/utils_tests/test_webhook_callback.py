"""Callback-path secrets: URL building, constant-time matching and redaction."""

from unittest.mock import patch

import pytest
from pydantic import SecretStr

from app.config import settings
from app.utils.webhook_callback import callback_token, callback_token_matches, callback_url, redact_callback_url

TOKEN = "3f9c1e7a5b2d4c8e9a0b1c2d3e4f5a6b"


def test_callback_url_carries_the_token_as_the_last_path_segment() -> None:
    with patch.object(settings, "api_base_url", "https://api.example.com"):
        url = callback_url("strava")

    token = callback_token("strava").get_secret_value()
    assert url == f"https://api.example.com/api/v1/providers/strava/webhooks/{token}"


def test_token_is_per_provider_and_follows_secret_key() -> None:
    strava = callback_token("strava")

    assert callback_token("garmin") != strava
    with patch.object(settings, "secret_key", "x" * 64):
        assert callback_token("strava") != strava


@pytest.mark.parametrize(
    ("expected", "provided", "matches"),
    [
        (SecretStr(TOKEN), TOKEN, True),
        (SecretStr(TOKEN), TOKEN.upper(), False),
        (SecretStr(TOKEN), "", False),
        (SecretStr(TOKEN), None, False),
        (SecretStr(TOKEN), "żółw", False),
        (SecretStr(""), "", False),
        (None, TOKEN, False),
    ],
)
def test_token_matching(expected: SecretStr | None, provided: str | None, matches: bool) -> None:
    assert callback_token_matches(expected, provided) is matches


@pytest.mark.parametrize(
    ("url", "redacted"),
    [
        (
            f"https://api.example.com/api/v1/providers/strava/webhooks/{TOKEN}",
            "https://api.example.com/api/v1/providers/strava/webhooks/redacted",
        ),
        (
            f"/api/v1/providers/strava/webhooks/{TOKEN}?hub.mode=subscribe",
            "/api/v1/providers/strava/webhooks/redacted?hub.mode=subscribe",
        ),
        ("/api/v1/providers/strava/webhooks", "/api/v1/providers/strava/webhooks"),
        ("/api/v1/providers/strava/webhooks/subscriptions", "/api/v1/providers/strava/webhooks/subscriptions"),
        (
            "/api/v1/providers/strava/webhooks/subscriptions/382914",
            "/api/v1/providers/strava/webhooks/subscriptions/382914",
        ),
    ],
)
def test_redaction_hides_only_the_token(url: str, redacted: str) -> None:
    assert redact_callback_url(url) == redacted
