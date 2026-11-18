"""Tests for scripts/garmin_webhook_url.py: the operator pastes its output into the Garmin portal."""

from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.services.providers.garmin.webhook_handler import WEBHOOK_URL_COMMAND
from app.utils.webhook_callback import callback_token
from scripts.garmin_webhook_url import main


def test_prints_the_callback_url_alone_on_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    with patch.object(settings, "api_base_url", "https://api.example.com"):
        main()

    out, err = capsys.readouterr()
    token = callback_token("garmin").get_secret_value()
    assert out == f"https://api.example.com/api/v1/providers/garmin/webhooks/{token}\n"
    assert "every data type" in err
    assert "Warning" not in err
    assert token not in err


@pytest.mark.parametrize(
    "base_url",
    [
        "http://localhost:8000",
        "http://api.example.com",
        "https://127.0.0.1",
        "https://localhost",
        "https://api.example.com:8443",
        "https://10.0.0.5",
        "https://192.168.1.20",
        "https://[::1]",
        "https://host.docker.internal",
        "https://api.example.com/",
        "https://example.com/open-wearables",
        "https://",
        "https://api.example.com?preview=1",
        "https://api.example.com?",
        "https://api.example.com#x",
    ],
)
def test_warns_when_api_base_url_cannot_reach_garmin(base_url: str, capsys: pytest.CaptureFixture[str]) -> None:
    """Garmin needs a public HTTPS URL; the default API_BASE_URL is http://localhost:8000."""
    with patch.object(settings, "api_base_url", base_url):
        main()

    out, err = capsys.readouterr()
    assert out.startswith(f"{base_url}/api/v1/providers/garmin/webhooks/")
    assert "Warning: API_BASE_URL" in err


@pytest.mark.parametrize("base_url", ["https://api.example.com", "https://api.example.com:443", "https://8.8.8.8"])
def test_no_warning_for_a_public_https_url(base_url: str, capsys: pytest.CaptureFixture[str]) -> None:
    with patch.object(settings, "api_base_url", base_url):
        main()

    assert "Warning" not in capsys.readouterr().err


def test_the_printed_url_is_accepted(client: TestClient, capsys: pytest.CaptureFixture[str]) -> None:
    main()
    path = urlsplit(capsys.readouterr().out.strip()).path

    with (
        patch.object(settings, "garmin_client_id", "test-client-id"),
        patch("app.services.providers.garmin.webhook_handler.celery_app") as celery,
        patch("app.services.providers.garmin.webhook_handler.store_raw_payload"),
    ):
        celery.send_task.return_value.id = "task-1"
        response = client.post(path, headers={"garmin-client-id": "test-client-id"}, json={"dailies": []})

    assert response.status_code == 200


def test_the_command_in_the_rejection_hint_runs_this_script() -> None:
    """Rejected Garmin requests log WEBHOOK_URL_COMMAND; it must not point at a renamed file."""
    script = WEBHOOK_URL_COMMAND.removeprefix("uv run python ")
    assert (Path(__file__).resolve().parents[2] / script).is_file()
