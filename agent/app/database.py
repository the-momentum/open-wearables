from collections.abc import AsyncIterator, Iterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import UUID as SQL_UUID
from sqlalchemy import Engine, Text, create_engine, inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    declared_attr,
    sessionmaker,
)

from app.config import settings
from app.utils.mappings_meta import AutoRelMeta

engine = create_engine(
    settings.db_uri,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    pool_recycle=3600,
)

async_engine = create_async_engine(
    settings.db_uri_async,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    pool_recycle=3600,
)


def _prepare_sessionmaker(engine: Engine) -> sessionmaker:
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


class BaseDbModel(DeclarativeBase, metaclass=AutoRelMeta):
    @declared_attr  # type: ignore
    def __tablename__(self) -> str:
        return self.__name__.lower()

    @property
    def id_str(self) -> str:
        identity = inspect(self).identity
        if identity is None:
            return "<unsaved>"
        return str(identity[0])

    def __repr__(self) -> str:
        mapper = inspect(self.__class__)
        fields = [f"{col.key}={repr(getattr(self, col.key, None))}" for col in mapper.columns]
        return f"<{self.__class__.__name__}({', '.join(fields)})>"

    type_annotation_map = {
        str: Text,
        UUID: SQL_UUID,
    }


SessionLocal = _prepare_sessionmaker(engine)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def _get_db_dependency() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    except Exception as exc:
        db.rollback()
        raise exc
    finally:
        db.close()


async def _get_async_db_dependency() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as exc:
            await session.rollback()
            raise exc


DbSession = Annotated[Session, Depends(_get_db_dependency)]
AsyncDbSession = Annotated[AsyncSession, Depends(_get_async_db_dependency)]
