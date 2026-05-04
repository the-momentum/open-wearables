"""Factory-boy factories for creating agent test data."""

from __future__ import annotations

from uuid import uuid4

import factory
from factory import LazyFunction, Sequence

from app.models.chat_session import Session
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.agent import ConversationStatus, MessageRole


class BaseFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "flush"


class ConversationFactory(BaseFactory):
    class Meta:
        model = Conversation

    user_id = LazyFunction(uuid4)
    status = ConversationStatus.ACTIVE
    summary = None


class SessionFactory(BaseFactory):
    class Meta:
        model = Session

    conversation = factory.SubFactory(ConversationFactory)
    active = True
    request_count = 0


class MessageFactory(BaseFactory):
    class Meta:
        model = Message

    conversation = factory.SubFactory(ConversationFactory)
    session = None
    role = MessageRole.USER
    content = Sequence(lambda n: f"Test message {n}")
