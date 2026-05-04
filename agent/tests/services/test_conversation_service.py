"""Tests for ConversationService."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.agent import ConversationStatus, MessageRole
from app.services.conversation import ConversationService
from tests.factories import ConversationFactory, SessionFactory


@pytest.fixture
def service(db: AsyncSession) -> ConversationService:
    return ConversationService(db)


class TestConversationServiceUpsert:
    async def test_creates_conversation_and_session_for_new_user(
        self, db: AsyncSession, service: ConversationService
    ) -> None:
        user_id = uuid4()

        conversation, session = await service.upsert(user_id)

        assert conversation.user_id == user_id
        assert conversation.status == ConversationStatus.ACTIVE
        assert session.conversation_id == conversation.id
        assert session.active is True

    async def test_reuses_active_conversation_creates_new_session(
        self, db: AsyncSession, service: ConversationService
    ) -> None:
        user_id = uuid4()
        conv = ConversationFactory(user_id=user_id, status=ConversationStatus.ACTIVE)
        await db.flush()

        conversation, session = await service.upsert(user_id)

        assert conversation.id == conv.id
        assert session.conversation_id == conv.id

    async def test_reuses_existing_active_session(self, db: AsyncSession, service: ConversationService) -> None:
        user_id = uuid4()
        conv = ConversationFactory(user_id=user_id, status=ConversationStatus.ACTIVE)
        sess = SessionFactory(conversation=conv, active=True)
        await db.flush()

        conversation, session = await service.upsert(user_id)

        assert conversation.id == conv.id
        assert session.id == sess.id

    async def test_valid_conversation_id_reuses_both(self, db: AsyncSession, service: ConversationService) -> None:
        user_id = uuid4()
        conv = ConversationFactory(user_id=user_id, status=ConversationStatus.ACTIVE)
        sess = SessionFactory(conversation=conv, active=True)
        await db.flush()

        conversation, session = await service.upsert(user_id, conversation_id=conv.id)

        assert conversation.id == conv.id
        assert session.id == sess.id

    async def test_mismatched_user_id_falls_through_to_new_conversation(
        self, db: AsyncSession, service: ConversationService
    ) -> None:
        # conversation belongs to a different user
        conv = ConversationFactory(user_id=uuid4(), status=ConversationStatus.ACTIVE)
        SessionFactory(conversation=conv, active=True)
        await db.flush()

        other_user = uuid4()
        conversation, session = await service.upsert(other_user, conversation_id=conv.id)

        # Should NOT reuse the mismatched conversation
        assert conversation.user_id == other_user
        assert conversation.id != conv.id


class TestConversationServiceGetActive:
    async def test_returns_valid_session_and_conversation(self, db: AsyncSession, service: ConversationService) -> None:
        user_id = uuid4()
        conv = ConversationFactory(user_id=user_id, status=ConversationStatus.ACTIVE)
        sess = SessionFactory(conversation=conv, active=True)
        await db.flush()

        conversation, session = await service.get_active(conv.id, user_id)

        assert conversation.id == conv.id
        assert session.id == sess.id

    async def test_raises_404_for_unknown_conversation(self, db: AsyncSession, service: ConversationService) -> None:
        with pytest.raises(HTTPException) as exc:
            await service.get_active(uuid4(), uuid4())

        assert exc.value.status_code == 404

    async def test_raises_403_for_wrong_user(self, db: AsyncSession, service: ConversationService) -> None:
        conv = ConversationFactory(user_id=uuid4(), status=ConversationStatus.ACTIVE)
        SessionFactory(conversation=conv, active=True)
        await db.flush()

        with pytest.raises(HTTPException) as exc:
            await service.get_active(conv.id, uuid4())

        assert exc.value.status_code == 403

    async def test_raises_410_for_closed_conversation(self, db: AsyncSession, service: ConversationService) -> None:
        user_id = uuid4()
        conv = ConversationFactory(user_id=user_id, status=ConversationStatus.CLOSED)
        SessionFactory(conversation=conv, active=True)
        await db.flush()

        with pytest.raises(HTTPException) as exc:
            await service.get_active(conv.id, user_id)

        assert exc.value.status_code == 410

    async def test_raises_410_for_inactive_session(self, db: AsyncSession, service: ConversationService) -> None:
        user_id = uuid4()
        conv = ConversationFactory(user_id=user_id, status=ConversationStatus.ACTIVE)
        SessionFactory(conversation=conv, active=False)
        await db.flush()

        with pytest.raises(HTTPException) as exc:
            await service.get_active(conv.id, user_id)

        assert exc.value.status_code == 410


class TestConversationServiceSaveMessages:
    async def test_persists_user_and_assistant_messages(self, db: AsyncSession, service: ConversationService) -> None:
        from app.repositories import message_repository

        user_id = uuid4()
        conv = ConversationFactory(user_id=user_id)
        sess = SessionFactory(conversation=conv)
        await db.flush()

        await service.save_messages(conv.id, sess.id, "Hello!", "Hi there!")

        messages = await message_repository.get_by_conversation_id(db, conv.id)
        assert len(messages) == 2
        assert messages[0].role == MessageRole.USER
        assert messages[0].content == "Hello!"
        assert messages[1].role == MessageRole.ASSISTANT
        assert messages[1].content == "Hi there!"

    async def test_increments_session_request_count(self, db: AsyncSession, service: ConversationService) -> None:
        from app.repositories import session_repository

        user_id = uuid4()
        conv = ConversationFactory(user_id=user_id)
        sess = SessionFactory(conversation=conv, request_count=0)
        await db.flush()

        await service.save_messages(conv.id, sess.id, "msg", "reply")

        refreshed = await session_repository.get_by_id(db, sess.id)
        assert refreshed.request_count == 1


class TestConversationServiceBuildHistory:
    async def test_returns_empty_for_no_messages(self, db: AsyncSession, service: ConversationService) -> None:
        conv = ConversationFactory()
        await db.flush()

        history = await service.build_history(conv)

        assert history == []

    async def test_returns_all_messages_under_threshold(self, db: AsyncSession, service: ConversationService) -> None:
        from app.repositories import message_repository

        conv = ConversationFactory()
        await db.flush()

        await message_repository.create(db, conv.id, MessageRole.USER, "Question")
        await message_repository.create(db, conv.id, MessageRole.ASSISTANT, "Answer")

        history = await service.build_history(conv)

        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Question"}
        assert history[1] == {"role": "assistant", "content": "Answer"}

    async def test_uses_existing_summary_when_over_threshold(
        self, db: AsyncSession, service: ConversationService
    ) -> None:
        from unittest.mock import patch

        from app.repositories import message_repository

        conv = ConversationFactory(summary="Old summary text")
        await db.flush()

        # Create 25 messages (over default threshold of 20)
        for i in range(25):
            role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
            await message_repository.create(db, conv.id, role, f"Message {i}")

        from app.config import settings

        with patch.object(settings, "history_summary_threshold", 20):
            history = await service.build_history(conv)

        # First element should be the summary injection
        assert history[0]["role"] == "system"
        assert "Old summary text" in history[0]["content"]
        # Remaining should be the recent window
        assert len(history) == 21  # 1 summary + 20 recent
