from collections.abc import Iterator
from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import UUID as SQL_UUID
from sqlalchemy import Date, DateTime, Engine, String, Text, create_engine, func, inspect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    declared_attr,
    mapped_column,
    sessionmaker,
)
from sqlalchemy.pool import NullPool

from app.config import settings
from app.schemas.auth import ConnectionStatus, LiveSyncMode, SDKTokenOrigin, TokenType
from app.schemas.enums import (
    AggregationMethod,
    ComputedBy,
    DataGranularity,
    HealthScoreCategory,
    PeriodKind,
    ProviderName,
)
from app.schemas.model_crud.user_management import InvitationStatus
from app.schemas.sync_status import SyncScope, SyncSource, SyncStatus
from app.utils.mappings_meta import AutoRelMeta

# Applied per connection, so no query can pin a pooled connection indefinitely:
# without it one slow statement holds its slot until the client gives up, and the
# rest of the pool queues behind it.
_CONNECT_ARGS = {"options": f"-c statement_timeout={settings.db_statement_timeout_ms}"}

# Two independent pools over the same database, so their bounds are budgeted
# together (see the notes on the settings). Both are explicit: leaving the async
# engine unconfigured silently adds SQLAlchemy's default 5 + 10 on top of whatever
# the sync engine is allowed.
engine = create_engine(
    settings.db_uri,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    connect_args=_CONNECT_ARGS,
)

# A pool_size of 0 is not "unbounded" to QueuePool — it means a pool that can never
# hand out a pooled connection — so an unused async engine has to be NullPool
# instead, which connects on demand and reserves nothing between uses.
_async_pool_kwargs: dict = (
    {"poolclass": NullPool}
    if settings.db_async_pool_size == 0
    else {
        "pool_size": settings.db_async_pool_size,
        "max_overflow": settings.db_async_max_overflow,
        "pool_timeout": settings.db_pool_timeout,
        "pool_recycle": settings.db_pool_recycle,
    }
)
async_engine = create_async_engine(
    settings.db_uri,
    pool_pre_ping=True,
    connect_args=_CONNECT_ARGS,
    **_async_pool_kwargs,
)


def _prepare_sessionmaker(engine: Engine) -> sessionmaker:
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


class BaseDbModel(DeclarativeBase, metaclass=AutoRelMeta):
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

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
        DataGranularity: String(32),
        InvitationStatus: String(50),
        ProviderName: String(50),
        HealthScoreCategory: String(32),
        TokenType: String(64),
        SDKTokenOrigin: String(32),
        AggregationMethod: String(32),
        PeriodKind: String(32),
        ComputedBy: String(32),
        SyncSource: String(32),
        SyncScope: String(32),
        SyncStatus: String(32),
    }


SessionLocal = _prepare_sessionmaker(engine)


def _get_db_dependency() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    except Exception as exc:
        db.rollback()
        raise exc
    finally:
        db.close()


DbSession = Annotated[Session, Depends(_get_db_dependency)]
