"""Tests for POST /api/v1/conversation and PATCH /api/v1/conversation/{id} routes."""

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import Session
from app.models.conversation import Conversation
from app.schemas.agent import ConversationStatus
from tests.factories import ConversationFactory, SessionFactory


class TestCreateOrGetConversation:
    def test_creates_new_conversation_for_new_user(self, client: TestClient, auth_headers: dict) -> None:
        response = client.post("/api/v1/conversation", json={}, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert "conversation_id" in data
        assert "created_at" in data

    def test_returns_existing_conversation_when_passed_valid_conversation_id(
        self,
        client: TestClient,
        auth_headers: dict,
        active_session: Session,
        active_conversation: Conversation,
        user_id: UUID,
    ) -> None:
        response = client.post(
            "/api/v1/conversation",
            json={"conversation_id": str(active_conversation.id)},
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["conversation_id"] == str(active_conversation.id)

    def test_creates_new_conversation_when_conversation_id_is_unknown(
        self, client: TestClient, auth_headers: dict
    ) -> None:
        response = client.post(
            "/api/v1/conversation",
            json={"conversation_id": str(uuid4())},
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert "conversation_id" in data

    def test_requires_auth(self, client: TestClient) -> None:
        response = client.post("/api/v1/conversation", json={})

        assert response.status_code == 401


class TestDeactivateConversation:
    def test_deactivates_own_conversation(
        self,
        client: TestClient,
        auth_headers: dict,
        active_session: Session,
        active_conversation: Conversation,
    ) -> None:
        response = client.patch(
            f"/api/v1/conversation/{active_conversation.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == str(active_conversation.id)

    def test_returns_404_for_unknown_conversation(self, client: TestClient, auth_headers: dict) -> None:
        response = client.patch(
            f"/api/v1/conversation/{uuid4()}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    async def test_returns_403_for_conversation_owned_by_other_user(
        self,
        client: TestClient,
        auth_headers: dict,
        db: AsyncSession,
    ) -> None:
        other_conv = ConversationFactory(user_id=uuid4(), status=ConversationStatus.ACTIVE)
        SessionFactory(conversation=other_conv, active=True)
        await db.flush()

        response = client.patch(
            f"/api/v1/conversation/{other_conv.id}",
            headers=auth_headers,
        )

        assert response.status_code == 403

    def test_requires_auth(self, client: TestClient, active_conversation: Conversation) -> None:
        response = client.patch(f"/api/v1/conversation/{active_conversation.id}")

        assert response.status_code == 401
