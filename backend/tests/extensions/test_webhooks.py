import re
from collections.abc import Iterator
from hashlib import sha256
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.extensions import webhooks
from app.integrations.celery.tasks import emit_webhook_event_task

_DECLARED = {"my_extension.thing.created": "A thing was created.", "my_extension.thing.deleted": "A thing was deleted."}
_CREATED = "my_extension.thing.created"
_SVIX_EVENT_ID = re.compile(r"[a-zA-Z0-9\-_.]+")


@pytest.fixture
def dispatch() -> Iterator[MagicMock]:
    with (
        patch.object(webhooks, "collect_webhook_event_types", return_value=_DECLARED),
        patch("app.services.outgoing_webhooks.events._dispatch") as dispatch,
    ):
        yield dispatch


@pytest.fixture
def send_task() -> Iterator[MagicMock]:
    with (
        patch.object(webhooks, "collect_webhook_event_types", return_value=_DECLARED),
        patch("app.services.outgoing_webhooks.svix.is_enabled", return_value=True),
        patch("app.services.outgoing_webhooks.events.celery_app") as celery_app,
    ):
        yield celery_app.send_task


def _keys(dispatch: MagicMock) -> list[str | None]:
    return [call.kwargs["idempotency_key"] for call in dispatch.call_args_list]


def _enqueued_keys(send_task: MagicMock) -> list[str | None]:
    return [call.kwargs["kwargs"]["idempotency_key"] for call in send_task.call_args_list]


def test_a_declared_event_is_dispatched_on_the_users_channel(dispatch: MagicMock) -> None:
    user_id = uuid4()

    webhooks.emit(_CREATED, {"thing_id": "t1"}, user_id=user_id, idempotency_key="thing.t1")

    dispatch.assert_called_once_with(
        _CREATED,
        {"type": _CREATED, "data": {"thing_id": "t1", "user_id": str(user_id)}},
        channels=[f"user.{user_id}"],
        idempotency_key="my_extension.thing.created.thing.t1",
    )


def test_the_same_key_on_two_event_types_gives_two_keys(dispatch: MagicMock) -> None:
    webhooks.emit("my_extension.thing.created", {}, idempotency_key="t1")
    webhooks.emit("my_extension.thing.deleted", {}, idempotency_key="t1")

    created, deleted = _keys(dispatch)
    assert created != deleted


def test_an_event_without_a_user_goes_to_no_channel(dispatch: MagicMock) -> None:
    webhooks.emit(_CREATED, {"thing_id": "t1"})

    assert dispatch.call_args.kwargs["channels"] is None
    assert dispatch.call_args.args[1] == {"type": _CREATED, "data": {"thing_id": "t1"}}


def test_an_undeclared_event_is_not_sent(dispatch: MagicMock) -> None:
    webhooks.emit("my_extension.thing.unknown", {})

    dispatch.assert_not_called()


def test_an_undeclared_event_alerts(dispatch: MagicMock) -> None:
    with patch.object(webhooks, "logger") as logger:
        webhooks.emit("my_extension.thing.unknown", {})

    assert logger.error.call_args.kwargs["alert"] is True


class TestKeylessEvents:
    def test_a_keyless_event_is_enqueued_with_a_key_of_its_type(self, send_task: MagicMock) -> None:
        webhooks.emit(_CREATED, {})

        (key,) = _enqueued_keys(send_task)
        assert key is not None
        assert key.startswith(f"{_CREATED}.")
        assert len(key) > len(f"{_CREATED}.")

    def test_two_keyless_events_get_different_keys(self, send_task: MagicMock) -> None:
        webhooks.emit(_CREATED, {})
        webhooks.emit(_CREATED, {})

        first, second = _enqueued_keys(send_task)
        assert first != second

    def test_a_retry_resends_the_key_the_event_was_enqueued_with(self, send_task: MagicMock) -> None:
        webhooks.emit(_CREATED, {})
        enqueued = send_task.call_args.kwargs
        developers = [MagicMock(id=uuid4(), email="dev1@example.com"), MagicMock(id=uuid4(), email="dev2@example.com")]

        with (
            patch.object(emit_webhook_event_task, "developer_service") as developer_service,
            patch.object(emit_webhook_event_task, "svix_service") as svix_service,
        ):
            developer_service.crud.get_all.return_value = developers
            # The second developer fails once, so the retry sends to both again; the first must see the same event id.
            svix_service.send.side_effect = [MagicMock(), None, MagicMock(), MagicMock()]
            emit_webhook_event_task.emit_webhook_event.apply(args=enqueued["args"], kwargs=enqueued["kwargs"])

        keys = [call.kwargs["idempotency_key"] for call in svix_service.send.call_args_list]
        assert len(keys) == 4
        assert None not in keys
        assert len(set(keys)) == 1


class TestKeySanitising:
    def test_keys_differing_only_in_characters_outside_the_svix_charset_stay_different(
        self, dispatch: MagicMock
    ) -> None:
        webhooks.emit(_CREATED, {}, idempotency_key="rec:1")
        webhooks.emit(_CREATED, {}, idempotency_key="rec/1")

        colon, slash = _keys(dispatch)
        assert colon != slash
        assert all(key and _SVIX_EVENT_ID.fullmatch(key) for key in (colon, slash))

    def test_a_key_within_the_svix_charset_is_kept_as_it_is(self, dispatch: MagicMock) -> None:
        webhooks.emit(_CREATED, {}, idempotency_key="Rec-1_v2.final")

        assert _keys(dispatch) == [f"{_CREATED}.Rec-1_v2.final"]

    def test_a_key_outside_the_svix_charset_always_maps_to_the_same_key(self, dispatch: MagicMock) -> None:
        webhooks.emit(_CREATED, {}, idempotency_key="rec:1")
        webhooks.emit(_CREATED, {}, idempotency_key="rec:1")

        # A stable hash, not hash(): a retry may run in another process.
        assert _keys(dispatch) == [f"{_CREATED}.{sha256(b'rec:1').hexdigest()}"] * 2

    def test_a_key_too_long_for_a_svix_event_id_is_hashed(self, dispatch: MagicMock) -> None:
        long_key = "k" * 256  # within the charset, but Svix refuses an event id over 256 characters

        webhooks.emit(_CREATED, {}, idempotency_key=long_key)

        [key] = _keys(dispatch)
        assert key == f"{_CREATED}.{sha256(long_key.encode()).hexdigest()}"
        assert len(key) <= 256
