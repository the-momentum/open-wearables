"""Tests for MessageRepository."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import message_repository
from app.schemas.agent import MessageRole
from tests.factories import ConversationFactory, SessionFactory


class TestMessageRepositoryCreate:
    async def test_create_user_message(self, db: AsyncSession) -> None:
        conv = ConversationFactory()
        await db.flush()

        msg = await message_repository.create(db, conv.id, MessageRole.USER, "Hello!")

        assert msg.id is not None
        assert msg.conversation_id == conv.id
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello!"
        assert msg.session_id is None

    async def test_create_assistant_message(self, db: AsyncSession) -> None:
        conv = ConversationFactory()
        await db.flush()

        msg = await message_repository.create(db, conv.id, MessageRole.ASSISTANT, "Hi there!")

        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "Hi there!"

    async def test_create_message_with_session_id(self, db: AsyncSession) -> None:
        conv = ConversationFactory()
        sess = SessionFactory(conversation=conv)
        await db.flush()

        msg = await message_repository.create(db, conv.id, MessageRole.USER, "Test", session_id=sess.id)

        assert msg.session_id == sess.id


class TestMessageRepositoryGetByConversationId:
    async def test_returns_messages_ordered_by_created_at(self, db: AsyncSession) -> None:
        conv = ConversationFactory()
        await db.flush()

        await message_repository.create(db, conv.id, MessageRole.USER, "First")
        await message_repository.create(db, conv.id, MessageRole.ASSISTANT, "Second")
        await message_repository.create(db, conv.id, MessageRole.USER, "Third")

        messages = await message_repository.get_by_conversation_id(db, conv.id)

        assert len(messages) == 3
        assert messages[0].content == "First"
        assert messages[1].content == "Second"
        assert messages[2].content == "Third"

    async def test_returns_empty_list_for_unknown_conversation(self, db: AsyncSession) -> None:
        from uuid import uuid4

        messages = await message_repository.get_by_conversation_id(db, uuid4())

        assert messages == []

    async def test_respects_limit(self, db: AsyncSession) -> None:
        conv = ConversationFactory()
        await db.flush()

        for i in range(5):
            await message_repository.create(db, conv.id, MessageRole.USER, f"Msg {i}")

        messages = await message_repository.get_by_conversation_id(db, conv.id, limit=3)

        assert len(messages) == 3

    async def test_does_not_return_messages_from_other_conversations(self, db: AsyncSession) -> None:
        conv1 = ConversationFactory()
        conv2 = ConversationFactory()
        await db.flush()

        await message_repository.create(db, conv1.id, MessageRole.USER, "Conv1 msg")
        await message_repository.create(db, conv2.id, MessageRole.USER, "Conv2 msg")

        messages = await message_repository.get_by_conversation_id(db, conv1.id)

        assert len(messages) == 1
        assert messages[0].content == "Conv1 msg"
