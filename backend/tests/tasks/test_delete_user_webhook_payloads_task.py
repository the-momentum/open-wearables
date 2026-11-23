"""Tests for deleting the outgoing webhook payloads of a deleted user from Svix."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, create_autospec, patch
from uuid import uuid4

import pytest
from celery.exceptions import Retry
from pytest_mock import MockerFixture
from sqlalchemy.orm import Session
from svix.api import BulkExpungeContentsOut, BulkExpungeStatus, ListResponseMessageOut, Message, MessageOut, Svix
from svix.api.errors.http_error import HttpError

from app.integrations.celery.tasks.delete_user_webhook_payloads_task import delete_user_webhook_payloads
from app.models import Developer
from app.services import user_service
from app.services.outgoing_webhooks import svix as svix_service
from tests.factories import UserFactory


def _http_error(status_code: int) -> HttpError:
    return HttpError.init_exception({"code": "err", "detail": "err"}, status_code)


def _page(ids: list[str], *, done: bool, iterator: str | None = None) -> ListResponseMessageOut:
    messages = [MessageOut(event_type="test", payload={}, id=msg_id, timestamp=datetime.now(UTC)) for msg_id in ids]
    return ListResponseMessageOut(data=messages, done=done, iterator=iterator)


@pytest.fixture
def mock_client() -> Generator[MagicMock, None, None]:
    mock = create_autospec(Svix, instance=True)
    mock.message = create_autospec(Message, instance=True)
    with patch("app.services.outgoing_webhooks.svix._client", mock):
        yield mock


class TestDeleteUserMessagePayloads:
    def test_lists_by_user_channel_across_pages_and_bulk_deletes(self, mock_client: MagicMock) -> None:
        user_id = uuid4()
        mock_client.message.list.side_effect = [
            _page(["msg_1", "msg_2"], done=False, iterator="it_1"),
            _page(["msg_3"], done=True),
        ]
        mock_client.message.bulk_expunge_content.return_value = BulkExpungeContentsOut(
            results={
                "msg_1": BulkExpungeStatus.EXPUNGED,
                "msg_2": BulkExpungeStatus.EXPUNGED,
                "msg_3": BulkExpungeStatus.NOT_FOUND,
            }
        )

        deleted = svix_service.delete_user_message_payloads("app_1", user_id)

        assert deleted == 2
        first_opts = mock_client.message.list.call_args_list[0].args[1]
        second_opts = mock_client.message.list.call_args_list[1].args[1]
        assert first_opts.channel == f"user.{user_id}"
        assert first_opts.iterator is None
        assert second_opts.iterator == "it_1"
        sent = mock_client.message.bulk_expunge_content.call_args.args[1]
        assert sent.ids == ["msg_1", "msg_2", "msg_3"]

    def test_batches_bulk_delete(self, mock_client: MagicMock) -> None:
        ids = [f"msg_{i}" for i in range(250)]
        mock_client.message.list.return_value = _page(ids, done=True)
        mock_client.message.bulk_expunge_content.return_value = BulkExpungeContentsOut(results={})

        svix_service.delete_user_message_payloads("app_1", uuid4())

        batch_sizes = [len(c.args[1].ids) for c in mock_client.message.bulk_expunge_content.call_args_list]
        assert batch_sizes == [100, 100, 50]

    def test_no_messages_skips_delete(self, mock_client: MagicMock) -> None:
        mock_client.message.list.return_value = _page([], done=True)

        assert svix_service.delete_user_message_payloads("app_1", uuid4()) == 0
        mock_client.message.bulk_expunge_content.assert_not_called()

    def test_falls_back_to_single_delete_on_older_servers(self, mock_client: MagicMock) -> None:
        mock_client.message.list.return_value = _page(["msg_1", "msg_2"], done=True)
        mock_client.message.bulk_expunge_content.side_effect = _http_error(404)

        assert svix_service.delete_user_message_payloads("app_1", uuid4()) == 2
        assert [c.args for c in mock_client.message.expunge_content.call_args_list] == [
            ("app_1", "msg_1"),
            ("app_1", "msg_2"),
        ]

    def test_other_errors_propagate(self, mock_client: MagicMock) -> None:
        mock_client.message.list.return_value = _page(["msg_1"], done=True)
        mock_client.message.bulk_expunge_content.side_effect = _http_error(500)

        with pytest.raises(HttpError):
            svix_service.delete_user_message_payloads("app_1", uuid4())

    def test_repeated_iterator_raises(self, mock_client: MagicMock) -> None:
        mock_client.message.list.return_value = _page(["msg_1"], done=False, iterator="it_1")

        with pytest.raises(RuntimeError):
            svix_service.delete_user_message_payloads("app_1", uuid4())
        assert mock_client.message.list.call_count == 2
        mock_client.message.bulk_expunge_content.assert_not_called()


class TestDeleteUserWebhookPayloadsTask:
    def test_deletes_in_every_developer_app(self, mocker: MockerFixture) -> None:
        mock_dev_service = mocker.patch(
            "app.integrations.celery.tasks.delete_user_webhook_payloads_task.developer_service", autospec=True
        )
        mock_svix = mocker.patch(
            "app.integrations.celery.tasks.delete_user_webhook_payloads_task.svix_service", autospec=True
        )
        dev1, dev2 = Developer(id=uuid4()), Developer(id=uuid4())
        mock_dev_service.crud.get_all.return_value = [dev1, dev2]
        mock_svix.delete_user_message_payloads.return_value = 3
        user_id = uuid4()

        result = delete_user_webhook_payloads(str(user_id))

        assert result["deleted"] == 6
        assert [c.args for c in mock_svix.delete_user_message_payloads.call_args_list] == [
            (str(dev1.id), user_id),
            (str(dev2.id), user_id),
        ]

    def test_skips_apps_missing_in_svix(self, mocker: MockerFixture) -> None:
        mock_dev_service = mocker.patch(
            "app.integrations.celery.tasks.delete_user_webhook_payloads_task.developer_service", autospec=True
        )
        mock_svix = mocker.patch(
            "app.integrations.celery.tasks.delete_user_webhook_payloads_task.svix_service", autospec=True
        )
        mock_dev_service.crud.get_all.return_value = [Developer(id=uuid4()), Developer(id=uuid4())]
        mock_svix.delete_user_message_payloads.side_effect = [_http_error(404), 2]

        result = delete_user_webhook_payloads(str(uuid4()))

        assert result == {"user_id": result["user_id"], "deleted": 2, "errors": []}

    def test_retries_when_an_app_fails(self, mocker: MockerFixture) -> None:
        mock_dev_service = mocker.patch(
            "app.integrations.celery.tasks.delete_user_webhook_payloads_task.developer_service", autospec=True
        )
        mock_svix = mocker.patch(
            "app.integrations.celery.tasks.delete_user_webhook_payloads_task.svix_service", autospec=True
        )
        mock_capture = mocker.patch(
            "app.integrations.celery.tasks.delete_user_webhook_payloads_task.logger", autospec=True
        )
        app_id = uuid4()
        mock_dev_service.crud.get_all.return_value = [Developer(id=app_id)]
        mock_svix.delete_user_message_payloads.side_effect = _http_error(500)

        with (
            patch.object(delete_user_webhook_payloads, "retry", autospec=True, side_effect=Retry()) as mock_retry,
            pytest.raises(Retry),
        ):
            delete_user_webhook_payloads(str(uuid4()))
        mock_retry.assert_called_once()
        mock_capture.error.assert_called_once()
        assert mock_capture.error.call_args.kwargs["exc_info"] is not None
        assert mock_capture.error.call_args.kwargs["app_id"] == str(app_id)

    def test_retries_when_loading_developers_fails(self, mocker: MockerFixture) -> None:
        mock_dev_service = mocker.patch(
            "app.integrations.celery.tasks.delete_user_webhook_payloads_task.developer_service", autospec=True
        )
        mock_svix = mocker.patch(
            "app.integrations.celery.tasks.delete_user_webhook_payloads_task.svix_service", autospec=True
        )
        mock_dev_service.crud.get_all.side_effect = ConnectionError("db down")

        with (
            patch.object(delete_user_webhook_payloads, "retry", autospec=True, side_effect=Retry()) as mock_retry,
            pytest.raises(Retry),
        ):
            delete_user_webhook_payloads(str(uuid4()))
        mock_retry.assert_called_once()
        mock_svix.delete_user_message_payloads.assert_not_called()

    def test_noop_when_svix_disabled(self, mocker: MockerFixture) -> None:
        mock_svix = mocker.patch(
            "app.integrations.celery.tasks.delete_user_webhook_payloads_task.svix_service", autospec=True
        )
        mock_svix.is_enabled.return_value = False

        result = delete_user_webhook_payloads(str(uuid4()))

        assert result["deleted"] == 0
        mock_svix.delete_user_message_payloads.assert_not_called()


class TestUserDeleteSchedulesPayloadDeletion:
    def test_schedules_payload_deletion_after_user_delete(self, mocker: MockerFixture, db: Session) -> None:
        mock_task = mocker.patch("app.services.user_service.delete_user_webhook_payloads", autospec=True)
        user = UserFactory()
        user_id = user.id

        with patch("app.services.user_service.svix_service.is_enabled", autospec=True, return_value=True):
            user_service.delete(db, user_id)

        assert user_service.get(db, user_id) is None
        mock_task.apply_async.assert_called_once()
        assert mock_task.apply_async.call_args.kwargs["args"] == [str(user_id)]

    def test_delete_succeeds_when_scheduling_fails(self, mocker: MockerFixture, db: Session) -> None:
        mock_task = mocker.patch("app.services.user_service.delete_user_webhook_payloads", autospec=True)
        mock_task.apply_async.side_effect = ConnectionError("broker down")
        user = UserFactory()
        user_id = user.id

        with patch("app.services.user_service.svix_service.is_enabled", autospec=True, return_value=True):
            user_service.delete(db, user_id)

        assert user_service.get(db, user_id) is None

    def test_skips_when_svix_disabled(self, mocker: MockerFixture, db: Session) -> None:
        mock_task = mocker.patch("app.services.user_service.delete_user_webhook_payloads", autospec=True)
        user = UserFactory()

        with patch("app.services.user_service.svix_service.is_enabled", autospec=True, return_value=False):
            user_service.delete(db, user.id)

        mock_task.apply_async.assert_not_called()
