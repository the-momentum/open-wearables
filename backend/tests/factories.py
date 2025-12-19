"""
Factory-boy factories for creating test data.

Usage:
    from tests.factories import UserFactory, DeveloperFactory
    user = UserFactory()  # Session set automatically via conftest fixture
    developer = DeveloperFactory(email="custom@example.com")
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

import factory
from factory import LazyAttribute, LazyFunction, Sequence

from app.models import (
    ApiKey,
    Application,
    DataPointSeries,
    Developer,
    EventRecord,
    EventRecordDetail,
    ExternalDeviceMapping,
    ProviderSetting,
    SeriesTypeDefinition,
    SleepDetails,
    User,
    UserConnection,
    WorkoutDetails,
)
from app.schemas.oauth import ConnectionStatus


class BaseFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Base factory for all SQLAlchemy models."""

    class Meta:
        abstract = True
        sqlalchemy_session = None  # Set per-test via conftest fixture
        sqlalchemy_session_persistence = "flush"  # Don't commit, let test handle rollback


class SeriesTypeDefinitionFactory(BaseFactory):
    """Factory for SeriesTypeDefinition model.

    Note: heart_rate and other standard series types are seeded at session scope.
    Use get_or_create_heart_rate() for tests that need the heart_rate type.
    """

    class Meta:
        model = SeriesTypeDefinition

    code = factory.Sequence(lambda n: f"test_series_type_{n}")
    unit = "test_unit"

    @classmethod
    def get_or_create_heart_rate(cls) -> SeriesTypeDefinition:
        """Get the pre-seeded heart_rate series type (ID=1)."""
        session = cls._meta.sqlalchemy_session
        if session:
            existing = session.query(SeriesTypeDefinition).filter(SeriesTypeDefinition.id == 1).first()
            if existing:
                return existing
        # Fallback: create new one (shouldn't happen with proper seeding)
        return cls(id=1, code="heart_rate", unit="bpm")

    @classmethod
    def get_or_create_steps(cls) -> SeriesTypeDefinition:
        """Get the pre-seeded steps series type (ID=80)."""
        session = cls._meta.sqlalchemy_session
        if session:
            existing = session.query(SeriesTypeDefinition).filter(SeriesTypeDefinition.id == 80).first()
            if existing:
                return existing
        # Fallback: create new one (shouldn't happen with proper seeding)
        return cls(id=80, code="steps", unit="count")


class UserFactory(BaseFactory):
    """Factory for User model."""

    class Meta:
        model = User

    id = LazyFunction(uuid4)
    created_at = LazyFunction(lambda: datetime.now(timezone.utc))
    email = factory.Faker("email")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    external_user_id = None


class DeveloperFactory(BaseFactory):
    """Factory for Developer model."""

    class Meta:
        model = Developer

    id = LazyFunction(uuid4)
    created_at = LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = LazyFunction(lambda: datetime.now(timezone.utc))
    email = factory.Faker("email")
    hashed_password = LazyAttribute(
        lambda o: f"hashed_{o.password}" if hasattr(o, "password") else "hashed_test_password",
    )

    class Params:
        password = "test_password"


class ApiKeyFactory(BaseFactory):
    """Factory for ApiKey model."""

    class Meta:
        model = ApiKey

    id = LazyFunction(lambda: f"sk-{uuid4().hex[:32]}")
    name = Sequence(lambda n: f"Test API Key {n}")
    created_at = LazyFunction(lambda: datetime.now(timezone.utc))

    @classmethod
    def _create(cls, model_class: type[ApiKey], *args: Any, **kwargs: Any) -> ApiKey:
        """Override create to handle developer relationship."""
        developer = kwargs.pop("developer", None)
        # Remove any stale created_by that might have been set
        kwargs.pop("created_by", None)
        if developer is None:
            # Create a developer if not provided
            developer = DeveloperFactory()
        kwargs["created_by"] = developer.id
        return super()._create(model_class, *args, **kwargs)


class ApplicationFactory(BaseFactory):
    """Factory for Application model (SDK apps)."""

    class Meta:
        model = Application

    id = LazyFunction(uuid4)
    app_id = LazyFunction(lambda: f"app_{uuid4().hex[:32]}")
    app_secret_hash = LazyAttribute(
        lambda o: f"hashed_{o.app_secret}" if hasattr(o, "app_secret") else "hashed_test_app_secret",
    )
    name = Sequence(lambda n: f"Test Application {n}")
    created_at = LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = LazyFunction(lambda: datetime.now(timezone.utc))

    class Params:
        app_secret = "test_app_secret"

    @classmethod
    def _create(cls, model_class: type[Application], *args: Any, **kwargs: Any) -> Application:
        """Override create to handle developer relationship."""
        developer = kwargs.pop("developer", None)
        # Remove any stale developer_id that might have been set
        kwargs.pop("developer_id", None)
        if developer is None:
            # Create a developer if not provided
            developer = DeveloperFactory()
        kwargs["developer_id"] = developer.id
        return super()._create(model_class, *args, **kwargs)


class ExternalDeviceMappingFactory(BaseFactory):
    """Factory for ExternalDeviceMapping model."""

    class Meta:
        model = ExternalDeviceMapping

    id = LazyFunction(uuid4)
    provider_name = "apple"
    device_id = LazyFunction(lambda: f"device_{uuid4().hex[:8]}")

    @classmethod
    def _create(
        cls,
        model_class: type[ExternalDeviceMapping],
        *args: Any,
        **kwargs: Any,
    ) -> ExternalDeviceMapping:
        """Override create to handle user relationship."""
        user = kwargs.pop("user", None)
        # Remove any stale user_id that might have been set
        kwargs.pop("user_id", None)
        if user is None:
            user = UserFactory()
        kwargs["user_id"] = user.id
        return super()._create(model_class, *args, **kwargs)


class UserConnectionFactory(BaseFactory):
    """Factory for UserConnection model."""

    class Meta:
        model = UserConnection

    id = LazyFunction(uuid4)
    provider = "garmin"
    provider_user_id = LazyFunction(lambda: f"provider_{uuid4().hex[:8]}")
    provider_username = factory.Faker("user_name")
    access_token = LazyFunction(lambda: f"access_{uuid4().hex}")
    refresh_token = LazyFunction(lambda: f"refresh_{uuid4().hex}")
    token_expires_at = LazyFunction(lambda: datetime(2025, 12, 31, tzinfo=timezone.utc))
    scope = "read_all"
    status = ConnectionStatus.ACTIVE
    last_synced_at = None
    created_at = LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = LazyFunction(lambda: datetime.now(timezone.utc))

    @classmethod
    def _create(cls, model_class: type[UserConnection], *args: Any, **kwargs: Any) -> UserConnection:
        """Override create to handle user relationship."""
        user = kwargs.pop("user", None)
        # Remove any stale user_id that might have been set
        kwargs.pop("user_id", None)
        if user is None:
            user = UserFactory()
        kwargs["user_id"] = user.id
        return super()._create(model_class, *args, **kwargs)


class EventRecordFactory(BaseFactory):
    """Factory for EventRecord model."""

    class Meta:
        model = EventRecord

    id = LazyFunction(uuid4)
    category = "workout"
    type = "running"
    source_name = "Apple Watch"
    duration_seconds = 3600
    start_datetime = LazyFunction(lambda: datetime.now(timezone.utc))
    end_datetime = LazyAttribute(
        lambda o: datetime.fromtimestamp(o.start_datetime.timestamp() + (o.duration_seconds or 3600), tz=timezone.utc),
    )

    @classmethod
    def _create(cls, model_class: type[EventRecord], *args: Any, **kwargs: Any) -> EventRecord:
        """Override create to handle mapping relationship and type_ alias."""
        mapping = kwargs.pop("mapping", None)
        # Remove any stale external_device_mapping_id that might have been set
        kwargs.pop("external_device_mapping_id", None)
        if mapping is None:
            mapping = ExternalDeviceMappingFactory()
        kwargs["external_device_mapping_id"] = mapping.id

        # Handle type_ alias
        if "type_" in kwargs:
            kwargs["type"] = kwargs.pop("type_")

        return super()._create(model_class, *args, **kwargs)


class EventRecordDetailFactory(BaseFactory):
    """Factory for EventRecordDetail model."""

    class Meta:
        model = EventRecordDetail

    detail_type = "workout"

    @classmethod
    def _create(
        cls,
        model_class: type[EventRecordDetail],
        *args: Any,
        **kwargs: Any,
    ) -> EventRecordDetail:
        """Override create to handle event_record relationship."""
        event_record = kwargs.pop("event_record", None)
        # Remove any stale record_id that might have been set
        kwargs.pop("record_id", None)
        if event_record is None:
            event_record = EventRecordFactory()
        kwargs["record_id"] = event_record.id
        return super()._create(model_class, *args, **kwargs)


class DataPointSeriesFactory(BaseFactory):
    """Factory for DataPointSeries model."""

    class Meta:
        model = DataPointSeries

    id = LazyFunction(uuid4)
    value = LazyFunction(lambda: Decimal("72.0"))
    recorded_at = LazyFunction(lambda: datetime.now(timezone.utc))

    @classmethod
    def _create(cls, model_class: type[DataPointSeries], *args: Any, **kwargs: Any) -> DataPointSeries:
        """Override create to handle relationships."""
        mapping = kwargs.pop("mapping", None)
        series_type = kwargs.pop("series_type", None)

        if mapping is None:
            mapping = ExternalDeviceMappingFactory()
        if series_type is None:
            # Use the pre-seeded heart_rate series type
            series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        kwargs["external_device_mapping_id"] = mapping.id
        kwargs["series_type_definition_id"] = series_type.id

        # Remove LazyAttribute placeholders that may have been set
        if "external_device_mapping_id" in kwargs and kwargs["external_device_mapping_id"] is None:
            kwargs.pop("external_device_mapping_id", None)
        if "series_type_definition_id" in kwargs and kwargs["series_type_definition_id"] is None:
            kwargs.pop("series_type_definition_id", None)

        kwargs["external_device_mapping_id"] = mapping.id
        kwargs["series_type_definition_id"] = series_type.id

        # Convert value to Decimal if needed
        if "value" in kwargs and not isinstance(kwargs["value"], Decimal):
            kwargs["value"] = Decimal(str(kwargs["value"]))

        return super()._create(model_class, *args, **kwargs)


class ProviderSettingFactory(BaseFactory):
    """Factory for ProviderSetting model."""

    class Meta:
        model = ProviderSetting

    provider = "garmin"
    is_enabled = True


class WorkoutDetailsFactory(BaseFactory):
    """Factory for WorkoutDetails model."""

    class Meta:
        model = WorkoutDetails

    heart_rate_avg = LazyFunction(lambda: Decimal("145.5"))
    heart_rate_max = 175
    heart_rate_min = 95
    steps_count = 8500

    @classmethod
    def _create(cls, model_class: type[WorkoutDetails], *args: Any, **kwargs: Any) -> WorkoutDetails:
        """Override create to handle event_record relationship."""
        event_record = kwargs.pop("event_record", None)
        # Remove any stale record_id that might have been set
        kwargs.pop("record_id", None)
        if event_record is None:
            event_record = EventRecordFactory(category="workout")
        kwargs["record_id"] = event_record.id

        # Convert heart_rate_avg to Decimal if needed
        if "heart_rate_avg" in kwargs and not isinstance(kwargs["heart_rate_avg"], Decimal):
            kwargs["heart_rate_avg"] = Decimal(str(kwargs["heart_rate_avg"]))

        return super()._create(model_class, *args, **kwargs)


class SleepDetailsFactory(BaseFactory):
    """Factory for SleepDetails model."""

    class Meta:
        model = SleepDetails

    sleep_total_duration_minutes = 480  # 8 hours
    sleep_deep_minutes = 120  # 2 hours
    sleep_light_minutes = 240  # 4 hours
    sleep_rem_minutes = 90  # 1.5 hours
    sleep_awake_minutes = 30  # 30 min

    @classmethod
    def _create(cls, model_class: type[SleepDetails], *args: Any, **kwargs: Any) -> SleepDetails:
        """Override create to handle event_record relationship."""
        event_record = kwargs.pop("event_record", None)
        # Remove any stale record_id that might have been set
        kwargs.pop("record_id", None)
        if event_record is None:
            event_record = EventRecordFactory(category="sleep", type="sleep")
        kwargs["record_id"] = event_record.id
        return super()._create(model_class, *args, **kwargs)


__all__ = [
    "BaseFactory",
    "SeriesTypeDefinitionFactory",
    "UserFactory",
    "DeveloperFactory",
    "ApiKeyFactory",
    "ApplicationFactory",
    "ExternalDeviceMappingFactory",
    "UserConnectionFactory",
    "EventRecordFactory",
    "EventRecordDetailFactory",
    "DataPointSeriesFactory",
    "ProviderSettingFactory",
    "WorkoutDetailsFactory",
    "SleepDetailsFactory",
]
