"""Tests for WithingsWebhookHandler.

Withings is notify-only: ``dispatch`` acknowledges fast and enqueues the shared
``process_webhook_push`` task; the actual REST fetch happens in ``process_payload``
(run by the Celery worker). Inbound-validation guards (invalid fields, profile
change, missing date range) short-circuit in ``dispatch`` and must NOT enqueue.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.schemas.auth import LiveSyncMode
from app.services.providers.withings.webhook_handler import WithingsWebhookHandler


def _handler(live_sync_mode: LiveSyncMode | None = LiveSyncMode.WEBHOOK) -> WithingsWebhookHandler:
    h = WithingsWebhookHandler(data_247=MagicMock(), workouts=MagicMock())
    h.connection_repo = MagicMock()
    h.connection_repo.get_by_provider_user_id.return_value = MagicMock(user_id=uuid4())
    h.provider_settings_repo = MagicMock()
    h.provider_settings_repo.get_all.return_value = (
        {"withings": SimpleNamespace(live_sync_mode=live_sync_mode)} if live_sync_mode is not None else {}
    )
    return h


# ---------------------------- inbound request ----------------------------


def test_parse_payload_reads_form_fields() -> None:
    h = _handler()
    body = b"userid=123&appli=1&startdate=1728000000&enddate=1728001000"
    payload = h.parse_payload(body)
    assert payload["userid"] == "123"
    assert payload["appli"] == "1"
    assert payload["startdate"] == "1728000000"


def test_verify_signature_accepts_wellformed_notification() -> None:
    h = _handler()
    assert h.verify_signature(MagicMock(), b"userid=123&appli=1&startdate=1&enddate=2") is True


def test_verify_signature_accepts_unknown_user_wellformed() -> None:
    # Unknown/disconnected users are acked 200 and ignored in the worker — never 401.
    h = _handler()
    assert h.verify_signature(MagicMock(), b"userid=999&appli=1&startdate=1&enddate=2") is True


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


@patch("app.services.providers.withings.webhook_handler.celery_app")
def test_dispatch_ignores_when_live_mode_is_pull(mock_celery: MagicMock) -> None:
    h = _handler(LiveSyncMode.PULL)
    result = h.dispatch(MagicMock(), {"userid": "123", "appli": "1", "startdate": "1", "enddate": "2"})
    assert result["status"] == "ignored"
    assert result["reason"] == "live_sync_mode_not_webhook"
    mock_celery.send_task.assert_not_called()


@patch("app.services.providers.withings.webhook_handler.celery_app")
def test_dispatch_defaults_to_pull_when_setting_missing(mock_celery: MagicMock) -> None:
    h = _handler(None)
    result = h.dispatch(MagicMock(), {"userid": "123", "appli": "1", "startdate": "1", "enddate": "2"})
    assert result["status"] == "ignored"
    assert result["reason"] == "live_sync_mode_not_webhook"
    mock_celery.send_task.assert_not_called()


@patch("app.services.providers.withings.webhook_handler.celery_app")
def test_dispatch_unknown_user_is_acked_without_enqueue(mock_celery: MagicMock) -> None:
    h = _handler()
    h.connection_repo.get_by_provider_user_id.return_value = None
    result = h.dispatch(MagicMock(), {"userid": "999", "appli": "1", "startdate": "1", "enddate": "2"})
    assert result["status"] == "ignored"
    assert result["reason"] == "user_not_found"
    mock_celery.send_task.assert_not_called()


@patch("app.services.providers.withings.webhook_handler.celery_app")
def test_dispatch_rejects_unbounded_window(mock_celery: MagicMock) -> None:
    h = _handler()
    result = h.dispatch(MagicMock(), {"userid": "123", "appli": "1", "startdate": "1", "enddate": "31536000"})
    assert result["status"] == "ignored"
    assert result["reason"] == "date_range_too_large"
    mock_celery.send_task.assert_not_called()


@patch("app.services.providers.withings.webhook_handler.celery_app")
def test_dispatch_accepts_activity_with_single_date(mock_celery: MagicMock) -> None:
    h = _handler()
    result = h.dispatch(MagicMock(), {"userid": "123", "appli": "16", "date": "2018-07-02"})
    assert result["status"] == "accepted"
    assert result["appli"] == 16
    mock_celery.send_task.assert_called_once()


@patch("app.services.providers.withings.webhook_handler.celery_app")
def test_dispatch_accepts_new_measure_categories(mock_celery: MagicMock) -> None:
    h = _handler()
    for appli in ("2", "58"):  # temperature, glucose
        mock_celery.reset_mock()
        result = h.dispatch(MagicMock(), {"userid": "1", "appli": appli, "startdate": "1", "enddate": "2"})
        assert result["status"] == "accepted"
        mock_celery.send_task.assert_called_once()


@patch("app.services.providers.withings.webhook_handler.store_raw_payload")
@patch("app.services.providers.withings.webhook_handler.celery_app")
def test_dispatch_does_not_store_raw_on_ack_path(mock_celery: MagicMock, mock_store: MagicMock) -> None:
    h = _handler()
    h.dispatch(MagicMock(), {"userid": "1", "appli": "1", "startdate": "1", "enddate": "2"})
    mock_store.assert_not_called()  # raw storage is the worker's job, off the budget


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
    assert h.data_247.save_sleep.call_args.kwargs["widen_ymd_window"] is True
    h.data_247.save_measures.assert_not_called()


def test_process_payload_appli_16_fetches_activity_and_workouts() -> None:
    h = _handler()
    h.data_247.save_activity.return_value = 5
    h.workouts.load_data.return_value = 3
    result = _process(h, "16")
    assert result["status"] == "processed"
    assert result["records_saved"] == 8  # 5 activity + 3 workouts
    h.data_247.save_activity.assert_called_once()
    assert h.data_247.save_activity.call_args.kwargs["widen_ymd_window"] is True
    h.workouts.load_data.assert_called_once()
    assert h.workouts.load_data.call_args.kwargs["widen_ymd_window"] is True


def test_process_payload_unknown_user_is_reported() -> None:
    h = _handler()
    h.connection_repo.get_by_provider_user_id.return_value = None
    payload = {"userid": "999", "appli": "1", "startdate": "1", "enddate": "2"}
    result = h.process_payload(MagicMock(), payload, "trace-1")
    assert result["status"] == "user_not_found"
    assert result["withings_user_id"] == "999"
    h.data_247.save_measures.assert_not_called()


def test_process_payload_ignores_when_live_mode_switched_to_pull() -> None:
    h = _handler(LiveSyncMode.PULL)
    h.connection_repo.get_by_provider_user_id.return_value = MagicMock(user_id=uuid4())
    payload = {"userid": "123", "appli": "1", "startdate": "1", "enddate": "2"}
    result = h.process_payload(MagicMock(), payload, "trace-1")
    assert result["status"] == "ignored"
    assert result["reason"] == "live_sync_mode_not_webhook"
    h.data_247.save_measures.assert_not_called()


@patch("app.services.providers.withings.webhook_handler.store_raw_payload")
def test_process_payload_stores_raw_in_worker(mock_store: MagicMock) -> None:
    h = _handler()
    h.data_247.save_measures.return_value = 0
    _process(h, "1")
    mock_store.assert_called_once()


def test_process_payload_appli_16_single_date_fetches_activity_and_workouts() -> None:
    h = _handler()
    h.connection_repo.get_by_provider_user_id.return_value = MagicMock(user_id=uuid4())
    h.data_247.save_activity.return_value = 5
    h.workouts.load_data.return_value = 3
    result = h.process_payload(MagicMock(), {"userid": "1", "appli": "16", "date": "2018-07-02"}, "t")
    assert result["records_saved"] == 8
    h.data_247.save_activity.assert_called_once()
    h.workouts.load_data.assert_called_once()


def test_process_payload_new_categories_go_to_measures() -> None:
    for appli in ("2", "58"):
        h = _handler()
        h.data_247.save_measures.return_value = 1
        result = _process(h, appli)
        assert result["domain"] == "measures"
        h.data_247.save_measures.assert_called_once()
