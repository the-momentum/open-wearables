from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.providers.google_health import webhook_handler
from app.services.providers.google_health.webhook_handler import GoogleWebhookHandler
from app.utils.exceptions import ReauthRequiredError


def test_a_dead_grant_in_a_batch_is_reported_and_the_rest_goes_on() -> None:
    """The grant is already revoked, so it is an expected state rather than an error for Sentry."""
    handler = GoogleWebhookHandler(MagicMock(), MagicMock())
    user_id = uuid4()
    outcomes = [ReauthRequiredError("google_health", user_id, "reconnection required"), {"records_saved": 2}]

    with (
        patch.object(GoogleWebhookHandler, "_process_one", side_effect=outcomes),
        patch.object(webhook_handler, "log_and_capture_error") as capture,
    ):
        result = handler.process_payload(MagicMock(), [{}, {}], "trace")

    capture.assert_not_called()
    assert result["records_saved"] == 2
    assert result["results"][0] == {"status": "error", "error": "reauth_required", "user_id": str(user_id)}
