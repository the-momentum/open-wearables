from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.providers.withings.notify_service import WITHINGS_APPLI_SET, WithingsNotifyService


def test_appli_set_is_what_we_subscribe() -> None:
    # Official categories: 1 body, 4 blood pressure + HR, 16 activity (+workouts), 44 sleep.
    assert WITHINGS_APPLI_SET == [1, 4, 16, 44]


@patch("app.services.providers.withings.notify_service.withings_request")
def test_subscribe_user_fans_out_per_appli_bearer_only(mock_req: MagicMock) -> None:
    mock_req.return_value = {}
    svc = WithingsNotifyService()
    results = svc.subscribe_user(MagicMock(), uuid4(), MagicMock(), MagicMock(), "https://cb/withings")

    assert mock_req.call_count == len(WITHINGS_APPLI_SET)
    for call in mock_req.call_args_list:
        params = call.kwargs["params"]
        assert call.kwargs["action"] == "subscribe"
        assert params["callbackurl"] == "https://cb/withings"
        # notify uses the OAuth Bearer token only — no Signature v2 params per the docs.
        assert "signature" not in params
        assert "nonce" not in params
    assert len(results) == len(WITHINGS_APPLI_SET)
    sent_appli = {call.kwargs["params"]["appli"] for call in mock_req.call_args_list}
    assert sent_appli == set(WITHINGS_APPLI_SET)


@patch("app.integrations.celery.tasks.withings.subscribe_task.SessionLocal")
@patch("app.integrations.celery.tasks.withings.subscribe_task.ProviderFactory")
@patch("app.integrations.celery.tasks.withings.subscribe_task.WithingsNotifyService")
def test_subscribe_task_retries_when_all_fail(
    mock_svc_cls: MagicMock,
    mock_factory_cls: MagicMock,
    mock_session_local: MagicMock,
) -> None:
    """When every appli returns an error, the task should call self.retry."""
    from app.integrations.celery.tasks.withings.subscribe_task import subscribe_withings_user

    # All appli fail
    all_error = [{"appli": a, "status": "error", "error": "boom"} for a in WITHINGS_APPLI_SET]
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
    from app.integrations.celery.tasks.withings.subscribe_task import subscribe_withings_user

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
