from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.schemas.auth import LiveSyncMode
from app.services.providers.withings.applis import SUBSCRIBED_APPLIS
from app.services.providers.withings.notify_service import WithingsNotifyService


def _service() -> WithingsNotifyService:
    return WithingsNotifyService(connection_repo=MagicMock(), oauth=MagicMock())


def test_subscribe_fans_out_over_every_subscribed_appli() -> None:
    assert SUBSCRIBED_APPLIS == [1, 2, 4, 16, 44, 58]


@patch("app.services.providers.withings.notify_service.withings_request")
def test_subscribe_user_fans_out_per_appli_bearer_only(mock_req: MagicMock) -> None:
    mock_req.return_value = {}
    service = _service()
    results = service.subscribe_user(MagicMock(), uuid4(), "https://cb/withings?token=secret")

    assert mock_req.call_count == len(SUBSCRIBED_APPLIS)
    for call in mock_req.call_args_list:
        params = call.kwargs["params"]
        assert call.kwargs["action"] == "subscribe"
        assert params["callbackurl"] == "https://cb/withings?token=secret"
        # Notify uses the OAuth bearer token only; Signature v2 is not part of
        # the documented public-app subscription request.
        assert "signature" not in params
        assert "nonce" not in params
    assert len(results) == len(SUBSCRIBED_APPLIS)
    assert {call.kwargs["params"]["appli"] for call in mock_req.call_args_list} == set(SUBSCRIBED_APPLIS)


@patch("app.services.providers.withings.notify_service.withings_request")
def test_revoke_user_fans_out_per_appli(mock_req: MagicMock) -> None:
    mock_req.return_value = {}
    service = _service()
    results = service.revoke_user(MagicMock(), uuid4(), "https://cb/withings?token=secret")

    assert mock_req.call_count == len(SUBSCRIBED_APPLIS)
    for call in mock_req.call_args_list:
        params = call.kwargs["params"]
        assert call.kwargs["action"] == "revoke"
        assert params["callbackurl"] == "https://cb/withings?token=secret"
        assert "comment" not in params
    assert len(results) == len(SUBSCRIBED_APPLIS)


@patch("app.services.providers.withings.notify_service.withings_callback_url", return_value="https://cb?token=x")
@patch.object(WithingsNotifyService, "subscribe_user", return_value=[])
def test_sync_user_subscribes_for_webhook_mode(mock_subscribe: MagicMock, mock_url: MagicMock) -> None:
    service = _service()
    db = MagicMock()
    user_id = uuid4()

    service.sync_user(db, user_id, LiveSyncMode.WEBHOOK)

    mock_url.assert_called_once_with()
    mock_subscribe.assert_called_once_with(db, user_id, "https://cb?token=x")


@patch("app.services.providers.withings.notify_service.withings_callback_url", return_value="https://cb?token=x")
@patch.object(WithingsNotifyService, "revoke_user", return_value=[])
def test_sync_user_revokes_for_pull_mode(mock_revoke: MagicMock, mock_url: MagicMock) -> None:
    service = _service()
    db = MagicMock()
    user_id = uuid4()

    service.sync_user(db, user_id, LiveSyncMode.PULL)

    mock_url.assert_called_once_with()
    mock_revoke.assert_called_once_with(db, user_id, "https://cb?token=x")
