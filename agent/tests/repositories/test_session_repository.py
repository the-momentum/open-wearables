"""Tests for SessionRepository."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import session_repository
from tests.factories import ConversationFactory, SessionFactory


class TestSessionRepositoryCreate:
    async def test_create_returns_active_session(self, db: AsyncSession) -> None:
        conv = ConversationFactory()
        await db.flush()

        session = await session_repository.create(db, conv.id)

        assert session.id is not None
        assert session.conversation_id == conv.id
        assert session.active is True
        assert session.request_count == 0

    async def test_create_multiple_sessions_for_same_conversation(self, db: AsyncSession) -> None:
        conv = ConversationFactory()
        await db.flush()

        s1 = await session_repository.create(db, conv.id)
        s2 = await session_repository.create(db, conv.id)

        assert s1.id != s2.id


class TestSessionRepositoryGetById:
    async def test_get_existing_returns_session(self, db: AsyncSession) -> None:
        sess = SessionFactory()
        await db.flush()

        result = await session_repository.get_by_id(db, sess.id)

        assert result is not None
        assert result.id == sess.id

    async def test_get_nonexistent_returns_none(self, db: AsyncSession) -> None:
        result = await session_repository.get_by_id(db, uuid4())
        assert result is None


class TestSessionRepositoryGetActiveByConversationId:
    async def test_returns_active_session(self, db: AsyncSession) -> None:
        conv = ConversationFactory()
        sess = SessionFactory(conversation=conv, active=True)
        await db.flush()

        result = await session_repository.get_active_by_conversation_id(db, conv.id)

        assert result is not None
        assert result.id == sess.id

    async def test_ignores_inactive_session(self, db: AsyncSession) -> None:
        conv = ConversationFactory()
        SessionFactory(conversation=conv, active=False)
        await db.flush()

        result = await session_repository.get_active_by_conversation_id(db, conv.id)

        assert result is None

    async def test_returns_none_for_unknown_conversation(self, db: AsyncSession) -> None:
        result = await session_repository.get_active_by_conversation_id(db, uuid4())
        assert result is None


class TestSessionRepositoryDeactivate:
    async def test_deactivate_sets_active_false(self, db: AsyncSession) -> None:
        sess = SessionFactory(active=True)
        await db.flush()

        updated = await session_repository.deactivate(db, sess)

        assert updated.active is False

    async def test_deactivate_already_inactive_is_idempotent(self, db: AsyncSession) -> None:
        sess = SessionFactory(active=False)
        await db.flush()

        updated = await session_repository.deactivate(db, sess)

        assert updated.active is False


class TestSessionRepositoryIncrementRequestCount:
    async def test_increments_count(self, db: AsyncSession) -> None:
        sess = SessionFactory(request_count=0)
        await db.flush()

        await session_repository.increment_request_count(db, sess)

        assert sess.request_count == 1

    async def test_increments_from_nonzero(self, db: AsyncSession) -> None:
        sess = SessionFactory(request_count=5)
        await db.flush()

        await session_repository.increment_request_count(db, sess)

        assert sess.request_count == 6


class TestSessionRepositoryDeactivateExpired:
    async def test_deactivates_stale_sessions(self, db: AsyncSession) -> None:
        sess = SessionFactory(active=True)
        await db.flush()

        # Back-date updated_at
        await db.execute(
            sa_update(type(sess))
            .where(type(sess).id == sess.id)
            .values(updated_at=datetime(2000, 1, 1, tzinfo=timezone.utc))
        )
        await db.commit()

        count = await session_repository.deactivate_expired(db, timedelta(minutes=10))

        assert count >= 1
        refreshed = await session_repository.get_by_id(db, sess.id)
        assert refreshed.active is False

    async def test_ignores_recently_active_sessions(self, db: AsyncSession) -> None:
        SessionFactory(active=True)
        await db.flush()

        count = await session_repository.deactivate_expired(db, timedelta(days=9999))

        assert count == 0

    async def test_ignores_already_inactive_sessions(self, db: AsyncSession) -> None:
        sess = SessionFactory(active=False)
        await db.flush()

        await db.execute(
            sa_update(type(sess))
            .where(type(sess).id == sess.id)
            .values(updated_at=datetime(2000, 1, 1, tzinfo=timezone.utc))
        )
        await db.commit()

        count = await session_repository.deactivate_expired(db, timedelta(seconds=0))

        assert count == 0
