"""
Polyfactory-based model factories for Open Wearables.

Unlike the old factory-boy factories, polyfactory introspects
SQLAlchemy ``Mapped[]`` annotations directly, so most columns are
generated automatically.  We only override fields that need stable
defaults or cross-model wiring.

Usage
─────
Factories are **not** instantiated directly.  Call the class method::

    user = UserFactory.create_sync(session=db)

The ``conftest._wire_factories`` autouse fixture calls ``set_session``
before every test, so you can also simply do::

    user = UserFactory.create_sync()
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from polyfactory.factories.sqlalchemy_factory import SQLAlchemyFactory
from sqlalchemy.orm import Session

from app.models import (
    ApiKey,
    Application,
    DataPointSeries,
    DataSource,
    Developer,
    EventRecord,
    EventRecordDetail,
    PersonalRecord,
    ProviderSetting,
    SeriesTypeDefinition,
    SleepDetails,
    User,
    UserConnection,
    WorkoutDetails,
)
from app.schemas.oauth import ConnectionStatus, ProviderName

# ── Session management ──────────────────────────────────────────────────────

_session: Session | None = None


def set_session(session: Session) -> None:
    """Called by conftest before each test."""
    global _session  # noqa: PLW0603
    _session = session


def clear_session() -> None:
    global _session  # noqa: PLW0603
    _session = None


class _Base(SQLAlchemyFactory[Any]):
    """
    Shared base for all model factories.

    * ``__is_base_factory__ = True`` prevents polyfactory from trying to
      instantiate ``_Base`` itself.
    * ``__set_relationships__`` is off so FK columns are set explicitly
      rather than via ORM relationship traversal (avoids double-inserts).
    """

    __is_base_factory__ = True
    __set_relationships__ = False
    __session__ = None  # overridden per-test via set_session()

    @classmethod
    def _get_session(cls) -> Session:
        if _session is None:
            msg = "Factory session not set — is the _wire_factories fixture active?"
            raise RuntimeError(msg)
        return _session

    @classmethod
    def create_sync(cls, **kwargs: Any) -> Any:
        """Build an instance and flush it to the test DB."""
        session = cls._get_session()
        instance = cls.build(**kwargs)
        session.add(instance)
        session.flush()
        return instance


# ════════════════════════════════════════════════════════════════════════════
#  Reference data
# ════════════════════════════════════════════════════════════════════════════


class SeriesTypeDefinitionFactory(_Base):
    __model__ = SeriesTypeDefinition

    @classmethod
    def build(cls, **kwargs: Any) -> SeriesTypeDefinition:
        kwargs.setdefault("code", f"test_series_{uuid4().hex[:8]}")
        kwargs.setdefault("unit", "unit")
        return SeriesTypeDefinition(**kwargs)

    @classmethod
    def get_or_create(cls, type_id: int, code: str, unit: str) -> SeriesTypeDefinition:
        """Return the pre-seeded row, or create a new one."""
        session = cls._get_session()
        existing = session.get(SeriesTypeDefinition, type_id)
        if existing:
            return existing
        return cls.create_sync(id=type_id, code=code, unit=unit)

    # Convenience accessors for the most-used types
    @classmethod
    def heart_rate(cls) -> SeriesTypeDefinition:
        return cls.get_or_create(1, "heart_rate", "bpm")

    @classmethod
    def steps(cls) -> SeriesTypeDefinition:
        return cls.get_or_create(80, "steps", "count")

    @classmethod
    def energy(cls) -> SeriesTypeDefinition:
        return cls.get_or_create(81, "energy", "kcal")

    @classmethod
    def resting_heart_rate(cls) -> SeriesTypeDefinition:
        return cls.get_or_create(2, "resting_heart_rate", "bpm")

    @classmethod
    def weight(cls) -> SeriesTypeDefinition:
        return cls.get_or_create(41, "weight", "kg")


# ════════════════════════════════════════════════════════════════════════════
#  Core domain
# ════════════════════════════════════════════════════════════════════════════


class UserFactory(_Base):
    __model__ = User

    @classmethod
    def build(cls, **kwargs: Any) -> User:
        kwargs.setdefault("id", uuid4())
        kwargs.setdefault("created_at", datetime.now(timezone.utc))
        kwargs.setdefault("email", f"user-{uuid4().hex[:8]}@test.local")
        kwargs.setdefault("first_name", "Test")
        kwargs.setdefault("last_name", "User")
        kwargs.setdefault("external_user_id", None)
        return User(**kwargs)


class PersonalRecordFactory(_Base):
    __model__ = PersonalRecord

    @classmethod
    def build(cls, **kwargs: Any) -> PersonalRecord:
        if "user" in kwargs:
            user = kwargs.pop("user")
            kwargs.setdefault("user_id", user.id)
        elif "user_id" not in kwargs:
            # Will be created on create_sync call
            user = UserFactory.create_sync()
            kwargs["user_id"] = user.id
        kwargs.setdefault("id", uuid4())
        kwargs.setdefault("birth_date", None)
        kwargs.setdefault("sex", None)
        kwargs.setdefault("gender", None)
        return PersonalRecord(**kwargs)


class DeveloperFactory(_Base):
    __model__ = Developer

    @classmethod
    def build(cls, **kwargs: Any) -> Developer:
        password = kwargs.pop("password", "test_password")
        kwargs.setdefault("id", uuid4())
        kwargs.setdefault("created_at", datetime.now(timezone.utc))
        kwargs.setdefault("updated_at", datetime.now(timezone.utc))
        kwargs.setdefault("email", f"dev-{uuid4().hex[:8]}@test.local")
        kwargs.setdefault("hashed_password", f"hashed_{password}")
        return Developer(**kwargs)


class ApiKeyFactory(_Base):
    __model__ = ApiKey

    @classmethod
    def build(cls, **kwargs: Any) -> ApiKey:
        if "developer" in kwargs:
            dev = kwargs.pop("developer")
            kwargs.setdefault("created_by", dev.id)
        elif "created_by" not in kwargs:
            dev = DeveloperFactory.create_sync()
            kwargs["created_by"] = dev.id
        kwargs.setdefault("id", f"sk-{uuid4().hex[:32]}")
        kwargs.setdefault("name", "Test API Key")
        kwargs.setdefault("created_at", datetime.now(timezone.utc))
        return ApiKey(**kwargs)


class ApplicationFactory(_Base):
    __model__ = Application

    @classmethod
    def build(cls, **kwargs: Any) -> Application:
        if "developer" in kwargs:
            dev = kwargs.pop("developer")
            kwargs.setdefault("developer_id", dev.id)
        elif "developer_id" not in kwargs:
            dev = DeveloperFactory.create_sync()
            kwargs["developer_id"] = dev.id

        app_secret = kwargs.pop("app_secret", "test_app_secret")
        kwargs.setdefault("app_secret_hash", f"hashed_{app_secret}")
        kwargs.setdefault("id", uuid4())
        kwargs.setdefault("app_id", f"app_{uuid4().hex[:32]}")
        kwargs.setdefault("name", "Test Application")
        kwargs.setdefault("created_at", datetime.now(timezone.utc))
        kwargs.setdefault("updated_at", datetime.now(timezone.utc))
        return Application(**kwargs)


# ════════════════════════════════════════════════════════════════════════════
#  Data layer
# ════════════════════════════════════════════════════════════════════════════


class DataSourceFactory(_Base):
    __model__ = DataSource

    @classmethod
    def build(cls, **kwargs: Any) -> DataSource:
        if "user" in kwargs:
            user = kwargs.pop("user")
            kwargs.setdefault("user_id", user.id)
        elif "user_id" not in kwargs:
            user = UserFactory.create_sync()
            kwargs["user_id"] = user.id
        kwargs.setdefault("id", uuid4())
        kwargs.setdefault("provider", ProviderName.APPLE)
        kwargs.setdefault("device_model", f"TestDevice-{uuid4().hex[:8]}")
        kwargs.setdefault("software_version", "1.0.0")
        kwargs.setdefault("source", "apple_health_sdk")
        kwargs.setdefault("device_type", "watch")
        kwargs.setdefault("user_connection_id", None)
        return DataSource(**kwargs)


class UserConnectionFactory(_Base):
    __model__ = UserConnection

    @classmethod
    def build(cls, **kwargs: Any) -> UserConnection:
        if "user" in kwargs:
            user = kwargs.pop("user")
            kwargs.setdefault("user_id", user.id)
        elif "user_id" not in kwargs:
            user = UserFactory.create_sync()
            kwargs["user_id"] = user.id
        kwargs.setdefault("id", uuid4())
        kwargs.setdefault("provider", "garmin")
        kwargs.setdefault("provider_user_id", f"prov_{uuid4().hex[:8]}")
        kwargs.setdefault("provider_username", "testuser")
        kwargs.setdefault("access_token", f"access_{uuid4().hex}")
        kwargs.setdefault("refresh_token", f"refresh_{uuid4().hex}")
        kwargs.setdefault("token_expires_at", datetime(2027, 12, 31, tzinfo=timezone.utc))
        kwargs.setdefault("scope", "read_all")
        kwargs.setdefault("status", ConnectionStatus.ACTIVE)
        kwargs.setdefault("last_synced_at", None)
        kwargs.setdefault("created_at", datetime.now(timezone.utc))
        kwargs.setdefault("updated_at", datetime.now(timezone.utc))
        return UserConnection(**kwargs)


# ════════════════════════════════════════════════════════════════════════════
#  Events & details
# ════════════════════════════════════════════════════════════════════════════


class EventRecordFactory(_Base):
    __model__ = EventRecord

    @classmethod
    def build(cls, **kwargs: Any) -> EventRecord:
        if "data_source" in kwargs:
            ds = kwargs.pop("data_source")
            kwargs.setdefault("data_source_id", ds.id)
        elif "data_source_id" not in kwargs:
            ds = DataSourceFactory.create_sync()
            kwargs["data_source_id"] = ds.id

        # Handle type_ alias (SQLAlchemy reserves `type`)
        if "type_" in kwargs:
            kwargs["type"] = kwargs.pop("type_")

        now = datetime.now(timezone.utc)
        duration = kwargs.get("duration_seconds", 3600)
        kwargs.setdefault("id", uuid4())
        kwargs.setdefault("category", "workout")
        kwargs.setdefault("type", "running")
        kwargs.setdefault("source_name", "Apple Watch")
        kwargs.setdefault("duration_seconds", duration)
        kwargs.setdefault("start_datetime", now)
        kwargs.setdefault(
            "end_datetime",
            datetime.fromtimestamp(
                kwargs["start_datetime"].timestamp() + (duration or 3600),
                tz=timezone.utc,
            ),
        )
        return EventRecord(**kwargs)


class EventRecordDetailFactory(_Base):
    __model__ = EventRecordDetail

    @classmethod
    def build(cls, **kwargs: Any) -> EventRecordDetail:
        if "event_record" in kwargs:
            er = kwargs.pop("event_record")
            kwargs.setdefault("record_id", er.id)
        elif "record_id" not in kwargs:
            er = EventRecordFactory.create_sync()
            kwargs["record_id"] = er.id
        kwargs.setdefault("detail_type", "workout")
        return EventRecordDetail(**kwargs)


class WorkoutDetailsFactory(_Base):
    __model__ = WorkoutDetails

    @classmethod
    def build(cls, **kwargs: Any) -> WorkoutDetails:
        if "event_record" in kwargs:
            er = kwargs.pop("event_record")
            kwargs.setdefault("record_id", er.id)
        elif "record_id" not in kwargs:
            er = EventRecordFactory.create_sync(category="workout")
            kwargs["record_id"] = er.id
        kwargs.setdefault("detail_type", "workout")
        kwargs.setdefault("heart_rate_avg", Decimal("145.5"))
        kwargs.setdefault("heart_rate_max", 175)
        kwargs.setdefault("heart_rate_min", 95)
        kwargs.setdefault("steps_count", 8500)
        return WorkoutDetails(**kwargs)


class SleepDetailsFactory(_Base):
    __model__ = SleepDetails

    @classmethod
    def build(cls, **kwargs: Any) -> SleepDetails:
        if "event_record" in kwargs:
            er = kwargs.pop("event_record")
            kwargs.setdefault("record_id", er.id)
        elif "record_id" not in kwargs:
            er = EventRecordFactory.create_sync(category="sleep", type="sleep")
            kwargs["record_id"] = er.id
        kwargs.setdefault("detail_type", "sleep")
        kwargs.setdefault("sleep_total_duration_minutes", 480)
        kwargs.setdefault("sleep_deep_minutes", 120)
        kwargs.setdefault("sleep_light_minutes", 240)
        kwargs.setdefault("sleep_rem_minutes", 90)
        kwargs.setdefault("sleep_awake_minutes", 30)
        return SleepDetails(**kwargs)


# ════════════════════════════════════════════════════════════════════════════
#  Time-series
# ════════════════════════════════════════════════════════════════════════════


class DataPointSeriesFactory(_Base):
    __model__ = DataPointSeries

    @classmethod
    def build(cls, **kwargs: Any) -> DataPointSeries:
        if "data_source" in kwargs:
            ds = kwargs.pop("data_source")
            kwargs.setdefault("data_source_id", ds.id)
        elif "data_source_id" not in kwargs:
            ds = DataSourceFactory.create_sync()
            kwargs["data_source_id"] = ds.id

        if "series_type" in kwargs:
            st = kwargs.pop("series_type")
            kwargs.setdefault("series_type_definition_id", st.id)
        elif "series_type_definition_id" not in kwargs:
            st = SeriesTypeDefinitionFactory.heart_rate()
            kwargs["series_type_definition_id"] = st.id

        value = kwargs.get("value", Decimal("72.0"))
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        kwargs["value"] = value

        kwargs.setdefault("id", uuid4())
        kwargs.setdefault("recorded_at", datetime.now(timezone.utc))
        return DataPointSeries(**kwargs)


# ════════════════════════════════════════════════════════════════════════════
#  Config / settings
# ════════════════════════════════════════════════════════════════════════════


class ProviderSettingFactory(_Base):
    __model__ = ProviderSetting

    @classmethod
    def build(cls, **kwargs: Any) -> ProviderSetting:
        kwargs.setdefault("provider", "garmin")
        kwargs.setdefault("is_enabled", True)
        return ProviderSetting(**kwargs)


# ── Public API ──────────────────────────────────────────────────────────────

__all__ = [
    "set_session",
    "clear_session",
    "SeriesTypeDefinitionFactory",
    "UserFactory",
    "PersonalRecordFactory",
    "DeveloperFactory",
    "ApiKeyFactory",
    "ApplicationFactory",
    "DataSourceFactory",
    "UserConnectionFactory",
    "EventRecordFactory",
    "EventRecordDetailFactory",
    "WorkoutDetailsFactory",
    "SleepDetailsFactory",
    "DataPointSeriesFactory",
    "ProviderSettingFactory",
]
