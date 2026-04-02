from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from app.database import AsyncSessionLocal
from app.repositories import chat_session_repository
from celery import shared_task

logger = logging.getLogger(__name__)

SESSION_MAX_AGE = timedelta(hours=1)


async def _deactivate_expired() -> int:
    async with AsyncSessionLocal() as db:
        return await chat_session_repository.deactivate_expired(db, SESSION_MAX_AGE)


@shared_task
def expire_sessions() -> None:
    deactivated = asyncio.run(_deactivate_expired())
    logger.info(f"Deactivated {deactivated} expired session(s)")
