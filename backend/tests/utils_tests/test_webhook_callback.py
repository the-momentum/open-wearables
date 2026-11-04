"""Callback-path secrets: URL building, constant-time matching, redaction and config validation."""

from unittest.mock import patch

import pytest
from pydantic import SecretStr, ValidationError

from app.config import Settings, settings
from app.utils.webhook_callback import callback_token_matches, callback_url, redact_callback_url

TOKEN = "3f9c1e7a5b2d4c8e9a0b1c2d3e4f5a6b"


def test_callback_url_carries_the_token_as_the_last_path_segment() -> None:
    with patch.object(settings, "api_base_url", "https://api.example.com"):
        url = callback_url("strava", SecretStr(TOKEN))

    assert url == f"https://api.example.com/api/v1/providers/strava/webhooks/{TOKEN}"


@pytest.mark.parametrize("token", [None, SecretStr("")])
def test_no_callback_url_without_a_token(token: SecretStr | None) -> None:
    assert callback_url("strava", token) is None


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


@pytest.mark.parametrize("token", ["with/slash", "with space", "with%2F", "żółw"])
def test_config_rejects_a_token_that_is_not_one_plain_path_segment(token: str) -> None:
    with pytest.raises(ValidationError, match="may contain only letters"):
        Settings(strava_webhook_token=token.ljust(40, "a"))


@pytest.mark.parametrize("token", ["abc", "subscriptions", TOKEN[:-1]])
def test_config_rejects_a_guessable_token(token: str) -> None:
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(strava_webhook_token=token)


@pytest.mark.parametrize("token", [TOKEN, "A-b_" * 8, ""])
def test_config_accepts_a_long_random_token_or_none(token: str) -> None:
    assert Settings(strava_webhook_token=token).strava_webhook_token == SecretStr(token)
