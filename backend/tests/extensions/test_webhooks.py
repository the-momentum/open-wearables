from collections.abc import Iterator
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.extensions import webhooks


@pytest.fixture
def dispatch() -> Iterator[MagicMock]:
    with (
        patch.object(webhooks, "collect_webhook_event_types", return_value={"agent.reply.completed": "Done."}),
        patch("app.services.outgoing_webhooks.events._dispatch") as dispatch,
    ):
        yield dispatch


def test_a_declared_event_is_dispatched_on_the_users_channel(dispatch: MagicMock) -> None:
    user_id = uuid4()

    webhooks.emit("agent.reply.completed", {"message_id": "m1"}, user_id=user_id, idempotency_key="agent:reply:m1")

    dispatch.assert_called_once_with(
        "agent.reply.completed",
        {"type": "agent.reply.completed", "data": {"message_id": "m1", "user_id": str(user_id)}},
        channels=[f"user.{user_id}"],
        idempotency_key="agent_reply_m1",
    )


def test_an_event_without_a_user_goes_to_no_channel(dispatch: MagicMock) -> None:
    webhooks.emit("agent.reply.completed", {"message_id": "m1"})

    assert dispatch.call_args.kwargs["channels"] is None
    assert dispatch.call_args.args[1] == {"type": "agent.reply.completed", "data": {"message_id": "m1"}}


def test_an_undeclared_event_is_not_sent(dispatch: MagicMock) -> None:
    webhooks.emit("agent.reply.unknown", {})

    dispatch.assert_not_called()
