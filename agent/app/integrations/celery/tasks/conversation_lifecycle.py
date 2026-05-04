"""Conversation lifecycle management task.

Runs every 5 minutes to:
1. Deactivate sessions idle longer than SESSION_TIMEOUT_MINUTES
2. Mark ACTIVE conversations as INACTIVE when their last session has been idle
3. Close INACTIVE conversations that have been idle for CONVERSATION_CLOSE_HOURS
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from app.config import settings
from app.database import AsyncSessionLocal
from app.repositories import conversation_repository, session_repository
from celery import shared_task

logger = logging.getLogger(__name__)


async def _run_lifecycle() -> None:
    session_timeout = timedelta(minutes=settings.session_timeout_minutes)
    close_after = timedelta(hours=settings.conversation_close_hours)

    async with AsyncSessionLocal() as db:
        # 1. Deactivate expired sessions
        deactivated_sessions = await session_repository.deactivate_expired(db, session_timeout)
        if deactivated_sessions:
            logger.info("Deactivated %d expired session(s)", deactivated_sessions)

        # 2. Mark stale ACTIVE conversations as INACTIVE
        marked_inactive = await conversation_repository.mark_inactive_stale(db, session_timeout)
        if marked_inactive:
            logger.info("Marked %d conversation(s) as INACTIVE", marked_inactive)

        # 3. Close INACTIVE conversations that have been idle too long
        closed = await conversation_repository.close_stale(db, close_after)
        if closed:
            logger.info("Closed %d stale conversation(s)", closed)


@shared_task
def manage_conversation_lifecycle() -> None:
    # asyncio.run() is safe for prefork (sync) Celery workers — do not switch to
    # gevent/eventlet without replacing this with a compatible async execution strategy.
    asyncio.run(_run_lifecycle())
