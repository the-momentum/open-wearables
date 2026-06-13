"""Tests for WithingsWebhookHandler.

Withings is notify-only: ``dispatch`` acknowledges fast and enqueues the shared
``process_webhook_push`` task; the actual REST fetch happens in ``process_payload``
(run by the Celery worker). Inbound-validation guards (invalid fields, profile
change, missing date range) short-circuit in ``dispatch`` and must NOT enqueue.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.providers.withings.webhook_handler import WithingsWebhookHandler


def _handler() -> WithingsWebhookHandler:
    h = WithingsWebhookHandler(data_247=MagicMock(), workouts=MagicMock())
    h.connection_repo = MagicMock()
    return h


# ---------------------------- inbound request ----------------------------


def test_parse_payload_reads_form_fields() -> None:
    h = _handler()
    body = b"userid=123&appli=1&startdate=1728000000&enddate=1728001000"
    payload = h.parse_payload(body)
    assert payload["userid"] == "123"
    assert payload["appli"] == "1"
    assert payload["startdate"] == "1728000000"


def test_verify_signature_accepts_known_user() -> None:
    h = _handler()
    h.connection_repo.get_by_provider_user_id.return_value = MagicMock()  # known
    body = b"userid=123&appli=1&startdate=1&enddate=2"
    assert h.verify_signature(MagicMock(), body) is True


def test_verify_signature_rejects_unknown_user() -> None:
    h = _handler()
    h.connection_repo.get_by_provider_user_id.return_value = None  # unknown
    body = b"userid=999&appli=1&startdate=1&enddate=2"
    assert h.verify_signature(MagicMock(), body) is False


def test_verify_signature_rejects_missing_userid() -> None:
    h = _handler()
    assert h.verify_signature(MagicMock(), b"appli=1") is False


def test_handle_challenge_returns_empty_dict_for_head_probe() -> None:
    # Withings fires a HEAD probe during subscribe; the handler must return 200.
    assert _handler().handle_challenge(MagicMock()) == {}


# ---------------------------- dispatch (enqueue) ----------------------------


@patch("app.services.providers.withings.webhook_handler.celery_app")
def test_dispatch_acknowledges_and_enqueues(mock_celery: MagicMock) -> None:
    h = _handler()
    payload = {"userid": "123", "appli": "1", "startdate": "1728000000", "enddate": "1728001000"}
    result = h.dispatch(MagicMock(), payload)
    assert result["status"] == "accepted"
    assert result["appli"] == 1
    mock_celery.send_task.assert_called_once()
    args, kwargs = mock_celery.send_task.call_args
    assert args[0].endswith("process_webhook_push")
    assert kwargs["args"][0] == "withings"
    assert kwargs["queue"] == "webhook_sync"
    # dispatch must NOT fetch synchronously
    h.data_247.save_measures.assert_not_called()


@patch("app.services.providers.withings.webhook_handler.celery_app")
def test_dispatch_ignores_invalid_payload_fields(mock_celery: MagicMock) -> None:
    h = _handler()
    payload = {"userid": "123", "appli": "x", "startdate": "not-a-number", "enddate": "1"}
    result = h.dispatch(MagicMock(), payload)
    assert result["status"] == "ignored"
    assert result["reason"] == "invalid_payload_fields"
    mock_celery.send_task.assert_not_called()


@patch("app.services.providers.withings.webhook_handler.celery_app")
def test_dispatch_ignores_profile_change(mock_celery: MagicMock) -> None:
    h = _handler()
    result = h.dispatch(MagicMock(), {"userid": "123", "appli": "46", "action": "unlink"})
    assert result["status"] == "ignored"
    assert result["reason"] == "profile_change"
    assert result["action"] == "unlink"
    mock_celery.send_task.assert_not_called()


@patch("app.services.providers.withings.webhook_handler.celery_app")
def test_dispatch_ignores_unhandled_appli(mock_celery: MagicMock) -> None:
    h = _handler()
    result = h.dispatch(MagicMock(), {"userid": "123", "appli": "99", "startdate": "1", "enddate": "2"})
    assert result["status"] == "ignored"
    assert "unhandled_appli" in result["reason"]
    mock_celery.send_task.assert_not_called()


@patch("app.services.providers.withings.webhook_handler.celery_app")
def test_dispatch_ignores_data_notification_without_date_range(mock_celery: MagicMock) -> None:
    """A data-domain notify without startdate must be rejected, not fetched from 1970."""
    h = _handler()
    result = h.dispatch(MagicMock(), {"userid": "123", "appli": "1"})
    assert result["status"] == "ignored"
    assert result["reason"] == "missing_date_range"
    mock_celery.send_task.assert_not_called()


# ---------------------------- process_payload (worker) ----------------------------


def _process(h: WithingsWebhookHandler, appli: str) -> dict:
    h.connection_repo.get_by_provider_user_id.return_value = MagicMock(user_id=uuid4())
    payload = {"userid": "123", "appli": appli, "startdate": "1728000000", "enddate": "1728001000"}
    return h.process_payload(MagicMock(), payload, "trace-1")


def test_process_payload_appli_1_goes_to_measures() -> None:
    h = _handler()
    h.data_247.save_measures.return_value = 1
    result = _process(h, "1")
    assert result["status"] == "processed"
    assert result["domain"] == "measures"
    h.data_247.save_measures.assert_called_once()
    h.data_247.save_sleep.assert_not_called()


def test_process_payload_appli_4_blood_pressure_goes_to_measures() -> None:
    h = _handler()
    h.data_247.save_measures.return_value = 2
    result = _process(h, "4")
    assert result["status"] == "processed"
    h.data_247.save_measures.assert_called_once()


def test_process_payload_appli_44_goes_to_sleep() -> None:
    h = _handler()
    h.data_247.save_sleep.return_value = 1
    result = _process(h, "44")
    assert result["status"] == "processed"
    h.data_247.save_sleep.assert_called_once()
    h.data_247.save_measures.assert_not_called()


def test_process_payload_appli_16_fetches_activity_and_workouts() -> None:
    h = _handler()
    h.data_247.save_activity.return_value = 5
    h.workouts.load_data.return_value = 3
    result = _process(h, "16")
    assert result["status"] == "processed"
    assert result["records_saved"] == 8  # 5 activity + 3 workouts
    h.data_247.save_activity.assert_called_once()
    h.workouts.load_data.assert_called_once()


def test_process_payload_unknown_user_is_reported() -> None:
    h = _handler()
    h.connection_repo.get_by_provider_user_id.return_value = None
    payload = {"userid": "999", "appli": "1", "startdate": "1", "enddate": "2"}
    result = h.process_payload(MagicMock(), payload, "trace-1")
    assert result["status"] == "user_not_found"
    assert result["withings_user_id"] == "999"
    h.data_247.save_measures.assert_not_called()
