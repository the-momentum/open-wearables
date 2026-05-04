"""API v1 specific fixtures."""

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import Session
from app.models.conversation import Conversation
from tests.factories import ConversationFactory, SessionFactory


@pytest.fixture
def user_id() -> UUID:
    return uuid4()


@pytest_asyncio.fixture
async def active_conversation(db: AsyncSession, user_id: UUID) -> Conversation:
    from app.schemas.agent import ConversationStatus

    conv = ConversationFactory(user_id=user_id, status=ConversationStatus.ACTIVE)
    await db.flush()
    return conv


@pytest_asyncio.fixture
async def active_session(db: AsyncSession, active_conversation: Conversation) -> Session:
    sess = SessionFactory(conversation=active_conversation, active=True)
    await db.flush()
    return sess
