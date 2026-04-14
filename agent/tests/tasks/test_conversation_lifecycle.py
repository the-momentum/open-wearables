"""Tests for the manage_conversation_lifecycle Celery task."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.agent import ConversationStatus
from tests.factories import ConversationFactory, SessionFactory


async def _backdate(db: AsyncSession, model_instance: Any, field: str, dt: datetime) -> None:
    """Helper to back-date a timestamp on an ORM instance."""
    await db.execute(
        sa_update(type(model_instance)).where(type(model_instance).id == model_instance.id).values(**{field: dt})
    )
    await db.commit()


class TestManageConversationLifecycle:
    async def test_deactivates_expired_sessions(self, db: AsyncSession) -> None:
        from app.integrations.celery.tasks.conversation_lifecycle import _run_lifecycle

        sess = SessionFactory(active=True)
        await db.flush()
        await _backdate(db, sess, "updated_at", datetime(2000, 1, 1, tzinfo=timezone.utc))

        with patch("app.integrations.celery.tasks.conversation_lifecycle.settings") as mock_settings:
            mock_settings.session_timeout_minutes = 10
            mock_settings.conversation_close_hours = 24

            with patch("app.integrations.celery.tasks.conversation_lifecycle.AsyncSessionLocal") as mock_session_local:
                mock_session_local.return_value.__aenter__ = AsyncMock(return_value=db)
                mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

                await _run_lifecycle()

        from app.repositories import session_repository

        refreshed = await session_repository.get_by_id(db, sess.id)
        assert refreshed.active is False

    async def test_marks_stale_conversations_inactive(self, db: AsyncSession) -> None:
        from app.integrations.celery.tasks.conversation_lifecycle import _run_lifecycle
        from app.repositories import conversation_repository

        conv = ConversationFactory(status=ConversationStatus.ACTIVE)
        await db.flush()
        await _backdate(db, conv, "updated_at", datetime(2000, 1, 1, tzinfo=timezone.utc))

        # Patch close_stale to a no-op so it does not interfere with the
        # mark-inactive assertion (mark_inactive_stale updates updated_at=now()
        # via SQLAlchemy onupdate, which can occasionally match the close window
        # depending on transaction timing).
        with patch("app.integrations.celery.tasks.conversation_lifecycle.settings") as mock_settings:
            mock_settings.session_timeout_minutes = 10
            mock_settings.conversation_close_hours = 24

            with patch("app.integrations.celery.tasks.conversation_lifecycle.AsyncSessionLocal") as mock_session_local:
                mock_session_local.return_value.__aenter__ = AsyncMock(return_value=db)
                mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

                with patch.object(conversation_repository, "close_stale", AsyncMock(return_value=0)):
                    await _run_lifecycle()

        refreshed = await conversation_repository.get_by_id(db, conv.id)
        assert refreshed.status == ConversationStatus.INACTIVE

    async def test_closes_long_inactive_conversations(self, db: AsyncSession) -> None:
        from app.integrations.celery.tasks.conversation_lifecycle import _run_lifecycle

        conv = ConversationFactory(status=ConversationStatus.INACTIVE)
        await db.flush()
        await _backdate(db, conv, "updated_at", datetime(2000, 1, 1, tzinfo=timezone.utc))

        with patch("app.integrations.celery.tasks.conversation_lifecycle.settings") as mock_settings:
            mock_settings.session_timeout_minutes = 10
            mock_settings.conversation_close_hours = 1

            with patch("app.integrations.celery.tasks.conversation_lifecycle.AsyncSessionLocal") as mock_session_local:
                mock_session_local.return_value.__aenter__ = AsyncMock(return_value=db)
                mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

                await _run_lifecycle()

        from app.repositories import conversation_repository

        refreshed = await conversation_repository.get_by_id(db, conv.id)
        assert refreshed.status == ConversationStatus.CLOSED

    async def test_does_not_affect_fresh_conversations(self, db: AsyncSession) -> None:
        from app.integrations.celery.tasks.conversation_lifecycle import _run_lifecycle

        conv = ConversationFactory(status=ConversationStatus.ACTIVE)
        await db.flush()
        # No backdating — conversation is fresh

        with patch("app.integrations.celery.tasks.conversation_lifecycle.settings") as mock_settings:
            mock_settings.session_timeout_minutes = 10
            mock_settings.conversation_close_hours = 24

            with patch("app.integrations.celery.tasks.conversation_lifecycle.AsyncSessionLocal") as mock_session_local:
                mock_session_local.return_value.__aenter__ = AsyncMock(return_value=db)
                mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

                await _run_lifecycle()

        from app.repositories import conversation_repository

        refreshed = await conversation_repository.get_by_id(db, conv.id)
        assert refreshed.status == ConversationStatus.ACTIVE
