from collections.abc import AsyncGenerator, Iterator
from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import UUID as SQL_UUID
from sqlalchemy import Date, DateTime, Engine, String, Text, create_engine, inspect
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    declared_attr,
    sessionmaker,
)

from app.config import settings
from app.schemas.auth import ConnectionStatus, LiveSyncMode, TokenType
from app.schemas.enums import AggregationMethod, HealthScoreCategory, ProviderName
from app.schemas.model_crud.user_management import InvitationStatus
from app.utils.mappings_meta import AutoRelMeta

engine = create_engine(
    settings.db_uri,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    pool_recycle=3600,
)
async_engine = create_async_engine(settings.db_uri)


def _prepare_sessionmaker(engine: Engine) -> sessionmaker:
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _prepare_async_sessionmaker(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


class BaseDbModel(DeclarativeBase, metaclass=AutoRelMeta):
    @declared_attr.directive
    def __tablename__(self) -> str:
        return self.__name__.lower()

    @property
    def id_str(self) -> str:
        return f"{inspect(self).identity[0]}"

    def __repr__(self) -> str:
        mapper = inspect(self.__class__)
        fields = [f"{col.key}={repr(getattr(self, col.key, None))}" for col in mapper.columns]
        return f"<{self.__class__.__name__}({', '.join(fields)})>"

    type_annotation_map = {
        str: Text,
        UUID: SQL_UUID,
        date: Date,
        datetime: DateTime(timezone=True),
        ConnectionStatus: String(64),
        LiveSyncMode: String(32),
        InvitationStatus: String(50),
        ProviderName: String(50),
        HealthScoreCategory: String(32),
        TokenType: String(64),
        AggregationMethod: String(32),
    }


SessionLocal = _prepare_sessionmaker(engine)
AsyncSessionLocal = _prepare_async_sessionmaker(async_engine)


def _get_db_dependency() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    except Exception as exc:
        db.rollback()
        raise exc
    finally:
        db.close()


async def _get_async_db_dependency() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


DbSession = Annotated[Session, Depends(_get_db_dependency)]
AsyncDbSession = Annotated[AsyncSession, Depends(_get_async_db_dependency)]
