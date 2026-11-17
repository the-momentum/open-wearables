from collections.abc import Iterator
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.extensions import webhooks

_DECLARED = {"my_extension.thing.created": "A thing was created.", "my_extension.thing.deleted": "A thing was deleted."}


@pytest.fixture
def dispatch() -> Iterator[MagicMock]:
    with (
        patch.object(webhooks, "collect_webhook_event_types", return_value=_DECLARED),
        patch("app.services.outgoing_webhooks.events._dispatch") as dispatch,
    ):
        yield dispatch


def test_a_declared_event_is_dispatched_on_the_users_channel(dispatch: MagicMock) -> None:
    user_id = uuid4()

    webhooks.emit("my_extension.thing.created", {"thing_id": "t1"}, user_id=user_id, idempotency_key="thing:t1")

    dispatch.assert_called_once_with(
        "my_extension.thing.created",
        {"type": "my_extension.thing.created", "data": {"thing_id": "t1", "user_id": str(user_id)}},
        channels=[f"user.{user_id}"],
        idempotency_key="my_extension.thing.created.thing_t1",
    )


def test_the_same_key_on_two_event_types_gives_two_keys(dispatch: MagicMock) -> None:
    webhooks.emit("my_extension.thing.created", {}, idempotency_key="t1")
    webhooks.emit("my_extension.thing.deleted", {}, idempotency_key="t1")

    created, deleted = (call.kwargs["idempotency_key"] for call in dispatch.call_args_list)
    assert created != deleted


def test_an_event_without_a_user_goes_to_no_channel(dispatch: MagicMock) -> None:
    webhooks.emit("my_extension.thing.created", {"thing_id": "t1"})

    assert dispatch.call_args.kwargs["channels"] is None
    assert dispatch.call_args.kwargs["idempotency_key"] is None
    assert dispatch.call_args.args[1] == {"type": "my_extension.thing.created", "data": {"thing_id": "t1"}}


def test_an_undeclared_event_is_not_sent(dispatch: MagicMock) -> None:
    webhooks.emit("my_extension.thing.unknown", {})

    dispatch.assert_not_called()
