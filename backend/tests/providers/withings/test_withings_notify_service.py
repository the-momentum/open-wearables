from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.integrations.celery.tasks.withings.subscribe_task import revoke_withings_user, subscribe_withings_user
from app.services.providers.withings.applis import SUBSCRIBED_APPLIS
from app.services.providers.withings.notify_service import WithingsNotifyService


def test_subscribe_fans_out_over_every_subscribed_appli() -> None:
    assert SUBSCRIBED_APPLIS == [1, 2, 4, 16, 44, 58]


@patch("app.services.providers.withings.notify_service.withings_request")
def test_subscribe_user_fans_out_per_appli_bearer_only(mock_req: MagicMock) -> None:
    mock_req.return_value = {}
    svc = WithingsNotifyService()
    results = svc.subscribe_user(MagicMock(), uuid4(), MagicMock(), MagicMock(), "https://cb/withings")

    assert mock_req.call_count == len(SUBSCRIBED_APPLIS)
    for call in mock_req.call_args_list:
        params = call.kwargs["params"]
        assert call.kwargs["action"] == "subscribe"
        assert params["callbackurl"] == "https://cb/withings"
        # notify uses the OAuth Bearer token only — no Signature v2 params per the docs.
        assert "signature" not in params
        assert "nonce" not in params
    assert len(results) == len(SUBSCRIBED_APPLIS)
    sent_appli = {call.kwargs["params"]["appli"] for call in mock_req.call_args_list}
    assert sent_appli == set(SUBSCRIBED_APPLIS)


@patch("app.services.providers.withings.notify_service.withings_request")
def test_revoke_user_fans_out_per_appli(mock_req: MagicMock) -> None:
    mock_req.return_value = {}
    svc = WithingsNotifyService()
    results = svc.revoke_user(MagicMock(), uuid4(), MagicMock(), MagicMock(), "https://cb/withings")

    assert mock_req.call_count == len(SUBSCRIBED_APPLIS)
    for call in mock_req.call_args_list:
        params = call.kwargs["params"]
        assert call.kwargs["action"] == "revoke"
        assert params["callbackurl"] == "https://cb/withings"
        assert "comment" not in params
    assert len(results) == len(SUBSCRIBED_APPLIS)


@patch("app.integrations.celery.tasks.withings.subscribe_task.SessionLocal")
@patch("app.integrations.celery.tasks.withings.subscribe_task.ProviderFactory")
@patch("app.integrations.celery.tasks.withings.subscribe_task.WithingsNotifyService")
def test_subscribe_task_retries_when_all_fail(
    mock_svc_cls: MagicMock,
    mock_factory_cls: MagicMock,
    mock_session_local: MagicMock,
) -> None:
    """When every appli returns an error, the task should call self.retry."""
    # All appli fail
    all_error = [{"appli": a, "status": "error", "error": "boom"} for a in SUBSCRIBED_APPLIS]
    mock_svc_instance = MagicMock()
    mock_svc_instance.subscribe_user.return_value = all_error
    mock_svc_cls.return_value = mock_svc_instance

    mock_strategy = MagicMock()
    mock_strategy.oauth = MagicMock()  # satisfy the assert
    mock_factory_cls.return_value.get_provider.return_value = mock_strategy

    # SessionLocal used as a context manager
    mock_session_local.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

    # Patch retry on the task itself to raise a sentinel exception
    sentinel = Exception("retry-called")
    with (
        patch.object(subscribe_withings_user, "retry", side_effect=sentinel),
        pytest.raises(Exception, match="retry-called"),
    ):
        # Run eagerly (apply() calls the underlying function via the bound task)
        subscribe_withings_user.apply(args=[str(uuid4())]).get()


@patch("app.integrations.celery.tasks.withings.subscribe_task.SessionLocal")
@patch("app.integrations.celery.tasks.withings.subscribe_task.ProviderFactory")
@patch("app.integrations.celery.tasks.withings.subscribe_task.WithingsNotifyService")
def test_subscribe_task_retries_on_partial_failure(
    mock_svc_cls: MagicMock,
    mock_factory_cls: MagicMock,
    mock_session_local: MagicMock,
) -> None:
    """One failed appli (e.g. sleep) must retry — subscribe is idempotent, and a
    user otherwise silently loses that notification category until reconnect."""
    partial = [
        {"appli": 1, "status": "subscribed"},
        {"appli": 4, "status": "subscribed"},
        {"appli": 16, "status": "subscribed"},
        {"appli": 44, "status": "error", "error": "boom"},
    ]
    mock_svc_instance = MagicMock()
    mock_svc_instance.subscribe_user.return_value = partial
    mock_svc_cls.return_value = mock_svc_instance

    mock_strategy = MagicMock()
    mock_strategy.oauth = MagicMock()
    mock_factory_cls.return_value.get_provider.return_value = mock_strategy

    mock_session_local.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

    sentinel = Exception("retry-called")
    with (
        patch.object(subscribe_withings_user, "retry", side_effect=sentinel),
        pytest.raises(Exception, match="retry-called"),
    ):
        subscribe_withings_user.apply(args=[str(uuid4())]).get()


@patch("app.integrations.celery.tasks.withings.subscribe_task.SessionLocal")
@patch("app.integrations.celery.tasks.withings.subscribe_task.ProviderFactory")
@patch("app.integrations.celery.tasks.withings.subscribe_task.WithingsNotifyService")
def test_revoke_task_revokes_then_succeeds(
    mock_svc_cls: MagicMock,
    mock_factory_cls: MagicMock,
    mock_session_local: MagicMock,
) -> None:
    """The per-user revoke task (fan-out target for a switch to PULL) runs revoke_user."""
    mock_svc_instance = MagicMock()
    mock_svc_instance.revoke_user.return_value = [{"appli": a, "status": "revoked"} for a in SUBSCRIBED_APPLIS]
    mock_svc_cls.return_value = mock_svc_instance

    mock_strategy = MagicMock()
    mock_strategy.oauth = MagicMock()
    mock_factory_cls.return_value.get_provider.return_value = mock_strategy

    mock_session_local.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

    result = revoke_withings_user.apply(args=[str(uuid4())]).get()

    assert all(r["status"] == "revoked" for r in result["results"])
    mock_svc_instance.revoke_user.assert_called_once()


@patch("app.integrations.celery.tasks.withings.subscribe_task.SessionLocal")
@patch("app.integrations.celery.tasks.withings.subscribe_task.ProviderFactory")
@patch("app.integrations.celery.tasks.withings.subscribe_task.WithingsNotifyService")
def test_revoke_task_retries_on_failure(
    mock_svc_cls: MagicMock,
    mock_factory_cls: MagicMock,
    mock_session_local: MagicMock,
) -> None:
    mock_svc_instance = MagicMock()
    mock_svc_instance.revoke_user.return_value = [{"appli": 1, "status": "error", "error": "boom"}]
    mock_svc_cls.return_value = mock_svc_instance

    mock_strategy = MagicMock()
    mock_strategy.oauth = MagicMock()
    mock_factory_cls.return_value.get_provider.return_value = mock_strategy

    mock_session_local.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

    with (
        patch.object(revoke_withings_user, "retry", side_effect=Exception("retry-called")),
        pytest.raises(Exception, match="retry-called"),
    ):
        revoke_withings_user.apply(args=[str(uuid4())]).get()
