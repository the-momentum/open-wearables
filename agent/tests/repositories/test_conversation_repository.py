"""Tests for ConversationRepository."""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import conversation_repository
from app.schemas.agent import ConversationStatus
from tests.factories import ConversationFactory


class TestConversationRepositoryCreate:
    async def test_create_returns_conversation(self, db: AsyncSession) -> None:
        user_id = uuid4()
        conv = await conversation_repository.create(db, user_id)

        assert conv.id is not None
        assert conv.user_id == user_id
        assert conv.status == ConversationStatus.ACTIVE
        assert conv.summary is None

    async def test_create_multiple_for_same_user(self, db: AsyncSession) -> None:
        user_id = uuid4()
        c1 = await conversation_repository.create(db, user_id)
        c2 = await conversation_repository.create(db, user_id)

        assert c1.id != c2.id


class TestConversationRepositoryGetById:
    async def test_get_existing_returns_conversation(self, db: AsyncSession) -> None:
        conv = ConversationFactory()
        await db.flush()

        result = await conversation_repository.get_by_id(db, conv.id)

        assert result is not None
        assert result.id == conv.id

    async def test_get_nonexistent_returns_none(self, db: AsyncSession) -> None:
        result = await conversation_repository.get_by_id(db, uuid4())
        assert result is None


class TestConversationRepositoryGetActiveByUserId:
    async def test_returns_active_conversation(self, db: AsyncSession) -> None:
        user_id = uuid4()
        conv = ConversationFactory(user_id=user_id, status=ConversationStatus.ACTIVE)
        await db.flush()

        result = await conversation_repository.get_active_by_user_id(db, user_id)

        assert result is not None
        assert result.id == conv.id

    async def test_ignores_inactive_conversation(self, db: AsyncSession) -> None:
        user_id = uuid4()
        ConversationFactory(user_id=user_id, status=ConversationStatus.INACTIVE)
        await db.flush()

        result = await conversation_repository.get_active_by_user_id(db, user_id)

        assert result is None

    async def test_ignores_closed_conversation(self, db: AsyncSession) -> None:
        user_id = uuid4()
        ConversationFactory(user_id=user_id, status=ConversationStatus.CLOSED)
        await db.flush()

        result = await conversation_repository.get_active_by_user_id(db, user_id)

        assert result is None

    async def test_returns_none_for_unknown_user(self, db: AsyncSession) -> None:
        result = await conversation_repository.get_active_by_user_id(db, uuid4())
        assert result is None


class TestConversationRepositoryUpdateStatus:
    async def test_update_status_to_inactive(self, db: AsyncSession) -> None:
        conv = ConversationFactory(status=ConversationStatus.ACTIVE)
        await db.flush()

        updated = await conversation_repository.update_status(db, conv, ConversationStatus.INACTIVE)

        assert updated.status == ConversationStatus.INACTIVE

    async def test_update_status_to_closed(self, db: AsyncSession) -> None:
        conv = ConversationFactory(status=ConversationStatus.INACTIVE)
        await db.flush()

        updated = await conversation_repository.update_status(db, conv, ConversationStatus.CLOSED)

        assert updated.status == ConversationStatus.CLOSED


class TestConversationRepositoryUpdateSummary:
    async def test_sets_summary_text(self, db: AsyncSession) -> None:
        conv = ConversationFactory()
        await db.flush()

        updated = await conversation_repository.update_summary(db, conv, "User asked about sleep.")

        assert updated.summary == "User asked about sleep."

    async def test_overwrites_existing_summary(self, db: AsyncSession) -> None:
        conv = ConversationFactory(summary="Old summary")
        await db.flush()

        updated = await conversation_repository.update_summary(db, conv, "New summary")

        assert updated.summary == "New summary"


class TestConversationRepositoryMarkInactiveStale:
    async def test_marks_stale_active_conversations_inactive(self, db: AsyncSession) -> None:
        from datetime import datetime, timezone

        from sqlalchemy import update as sa_update

        conv = ConversationFactory(status=ConversationStatus.ACTIVE)
        await db.flush()

        # Back-date updated_at to make it stale
        await db.execute(
            sa_update(type(conv))
            .where(type(conv).id == conv.id)
            .values(updated_at=datetime(2000, 1, 1, tzinfo=timezone.utc))
        )
        await db.commit()

        count = await conversation_repository.mark_inactive_stale(db, timedelta(minutes=10))

        assert count >= 1
        refreshed = await conversation_repository.get_by_id(db, conv.id)
        assert refreshed.status == ConversationStatus.INACTIVE

    async def test_ignores_recently_updated_conversations(self, db: AsyncSession) -> None:
        ConversationFactory(status=ConversationStatus.ACTIVE)
        await db.flush()

        # Use a tiny max_age so nothing should be stale
        count = await conversation_repository.mark_inactive_stale(db, timedelta(days=9999))

        assert count == 0


class TestConversationRepositoryCloseStale:
    async def test_closes_stale_inactive_conversations(self, db: AsyncSession) -> None:
        from datetime import datetime, timezone

        from sqlalchemy import update as sa_update

        conv = ConversationFactory(status=ConversationStatus.INACTIVE)
        await db.flush()

        await db.execute(
            sa_update(type(conv))
            .where(type(conv).id == conv.id)
            .values(updated_at=datetime(2000, 1, 1, tzinfo=timezone.utc))
        )
        await db.commit()

        count = await conversation_repository.close_stale(db, timedelta(hours=1))

        assert count >= 1
        refreshed = await conversation_repository.get_by_id(db, conv.id)
        assert refreshed.status == ConversationStatus.CLOSED

    async def test_ignores_active_conversations(self, db: AsyncSession) -> None:
        ConversationFactory(status=ConversationStatus.ACTIVE)
        await db.flush()

        count = await conversation_repository.close_stale(db, timedelta(seconds=0))

        assert count == 0
