"""Tests for POST /api/v1/chat/{conversation_id} route."""

from unittest.mock import MagicMock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import Session
from app.models.conversation import Conversation
from app.schemas.agent import ConversationStatus
from tests.factories import ConversationFactory, SessionFactory

CALLBACK_URL = "https://example.com/callback"


class TestSendMessage:
    def test_queues_task_and_returns_task_id(
        self,
        client: TestClient,
        auth_headers: dict,
        active_session: Session,
        active_conversation: Conversation,
        mock_celery: MagicMock,
    ) -> None:
        response = client.post(
            f"/api/v1/chat/{active_conversation.id}",
            json={"message": "How was my sleep?", "callback_url": CALLBACK_URL},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["task_id"] == "test-task-id"

    def test_calls_process_message_delay_with_correct_args(
        self,
        client: TestClient,
        auth_headers: dict,
        active_session: Session,
        active_conversation: Conversation,
        mock_celery: MagicMock,
    ) -> None:
        client.post(
            f"/api/v1/chat/{active_conversation.id}",
            json={"message": "Steps today?", "callback_url": CALLBACK_URL},
            headers=auth_headers,
        )

        mock_celery.delay.assert_called_once()
        call_kwargs = mock_celery.delay.call_args.kwargs
        assert call_kwargs["message"] == "Steps today?"
        assert call_kwargs["session_id"] == str(active_session.id)
        assert call_kwargs["conversation_id"] == str(active_conversation.id)

    def test_returns_404_for_unknown_conversation(self, client: TestClient, auth_headers: dict) -> None:
        response = client.post(
            f"/api/v1/chat/{uuid4()}",
            json={"message": "Hello", "callback_url": CALLBACK_URL},
            headers=auth_headers,
        )

        assert response.status_code == 404

    async def test_returns_410_for_closed_conversation(
        self,
        client: TestClient,
        auth_headers: dict,
        user_id: UUID,
        db: AsyncSession,
    ) -> None:
        closed_conv = ConversationFactory(user_id=user_id, status=ConversationStatus.CLOSED)
        SessionFactory(conversation=closed_conv, active=True)
        await db.flush()

        response = client.post(
            f"/api/v1/chat/{closed_conv.id}",
            json={"message": "Hello", "callback_url": CALLBACK_URL},
            headers=auth_headers,
        )

        assert response.status_code == 410

    async def test_returns_410_for_inactive_session(
        self,
        client: TestClient,
        auth_headers: dict,
        user_id: UUID,
        db: AsyncSession,
    ) -> None:
        conv = ConversationFactory(user_id=user_id, status=ConversationStatus.ACTIVE)
        SessionFactory(conversation=conv, active=False)
        await db.flush()

        response = client.post(
            f"/api/v1/chat/{conv.id}",
            json={"message": "Hello", "callback_url": CALLBACK_URL},
            headers=auth_headers,
        )

        assert response.status_code == 410

    def test_rejects_empty_message(
        self,
        client: TestClient,
        auth_headers: dict,
        active_session: Session,
        active_conversation: Conversation,
    ) -> None:
        response = client.post(
            f"/api/v1/chat/{active_conversation.id}",
            json={"message": "", "callback_url": CALLBACK_URL},
            headers=auth_headers,
        )

        assert response.status_code == 422

    def test_requires_auth(
        self, client: TestClient, active_session: Session, active_conversation: Conversation
    ) -> None:
        response = client.post(
            f"/api/v1/chat/{active_conversation.id}",
            json={"message": "Hello", "callback_url": CALLBACK_URL},
        )

        assert response.status_code == 401
