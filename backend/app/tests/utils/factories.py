"""
Factory functions for creating test data.

Following patterns from know-how-tests.md:
- Each factory creates a complete, valid entity
- Factories accept optional overrides via kwargs
- Factories handle database session and commit
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from faker import Faker
from sqlalchemy.orm import Session

from app.models import (
    ApiKey,
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

fake = Faker()


def create_series_type_definition(
    db: Session,
    *,
    code: str = "heart_rate",
    unit: str = "bpm",
    **kwargs,
) -> SeriesTypeDefinition:
    """Create a test series type definition."""
    # Check if it already exists
    existing = db.query(SeriesTypeDefinition).filter(SeriesTypeDefinition.code == code).first()
    if existing:
        return existing

    series_type = SeriesTypeDefinition(
        code=code,
        unit=unit,
    )
    db.add(series_type)
    db.commit()
    db.refresh(series_type)
    return series_type


def create_user(
    db: Session,
    *,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    external_user_id: str | None = None,
    **kwargs,
) -> User:
    """Create a test user."""
    user = User(
        id=kwargs.get("id", uuid4()),
        created_at=kwargs.get("created_at", datetime.now(timezone.utc)),
        email=email or fake.email(),
        first_name=first_name or fake.first_name(),
        last_name=last_name or fake.last_name(),
        external_user_id=external_user_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_developer(
    db: Session,
    *,
    email: str | None = None,
    password: str = "test_password",
    **kwargs,
) -> Developer:
    """Create a test developer with hashed password."""
    now = datetime.now(timezone.utc)
    developer = Developer(
        id=kwargs.get("id", uuid4()),
        created_at=kwargs.get("created_at", now),
        updated_at=kwargs.get("updated_at", now),
        email=email or fake.email(),
        hashed_password=f"hashed_{password}",  # Using simple hash from fixture
    )
    db.add(developer)
    db.commit()
    db.refresh(developer)
    return developer


def create_api_key(
    db: Session,
    *,
    developer: Developer | None = None,
    name: str | None = None,
    **kwargs,
) -> ApiKey:
    """Create a test API key."""
    if developer is None:
        developer = create_developer(db)

    key_id = kwargs.get("id", f"sk-{uuid4().hex[:32]}")
    api_key = ApiKey(
        id=key_id,
        name=name or f"Test API Key {fake.word()}",
        created_by=developer.id,
        created_at=kwargs.get("created_at", datetime.now(timezone.utc)),
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key


def create_external_device_mapping(
    db: Session,
    *,
    user: User | None = None,
    provider_id: str | None = None,
    device_id: str | None = None,
    **kwargs,
) -> ExternalDeviceMapping:
    """Create a test external device mapping."""
    if user is None:
        user = create_user(db)

    mapping = ExternalDeviceMapping(
        id=kwargs.get("id", uuid4()),
        user_id=user.id,
        provider_id=provider_id or "apple",
        device_id=device_id or f"device_{uuid4().hex[:8]}",
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


def create_user_connection(
    db: Session,
    *,
    user: User | None = None,
    provider: str = "garmin",
    status: ConnectionStatus = ConnectionStatus.ACTIVE,
    **kwargs,
) -> UserConnection:
    """Create a test user connection to a provider."""
    if user is None:
        user = create_user(db)

    now = datetime.now(timezone.utc)
    connection = UserConnection(
        id=kwargs.get("id", uuid4()),
        user_id=user.id,
        provider=provider,
        provider_user_id=kwargs.get("provider_user_id", f"provider_{uuid4().hex[:8]}"),
        provider_username=kwargs.get("provider_username", fake.user_name()),
        access_token=kwargs.get("access_token", f"access_{uuid4().hex}"),
        refresh_token=kwargs.get("refresh_token", f"refresh_{uuid4().hex}"),
        token_expires_at=kwargs.get("token_expires_at", datetime(2025, 12, 31, tzinfo=timezone.utc)),
        scope=kwargs.get("scope", "read_all"),
        status=status,
        last_synced_at=kwargs.get("last_synced_at"),
        created_at=kwargs.get("created_at", now),
        updated_at=kwargs.get("updated_at", now),
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


def create_event_record(
    db: Session,
    *,
    mapping: ExternalDeviceMapping | None = None,
    category: str = "workout",
    type_: str | None = "running",
    source_name: str = "Apple Watch",
    start_datetime: datetime | None = None,
    end_datetime: datetime | None = None,
    duration_seconds: int | None = 3600,
    **kwargs,
) -> EventRecord:
    """Create a test event record (workout/activity)."""
    if mapping is None:
        mapping = create_external_device_mapping(db)

    now = datetime.now(timezone.utc)
    start = start_datetime or now
    end = end_datetime or datetime.fromtimestamp(start.timestamp() + (duration_seconds or 3600), tz=timezone.utc)

    record = EventRecord(
        id=kwargs.get("id", uuid4()),
        external_mapping_id=mapping.id,
        category=category,
        type=type_,
        source_name=source_name,
        duration_seconds=duration_seconds,
        start_datetime=start,
        end_datetime=end,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def create_event_record_detail(
    db: Session,
    *,
    event_record: EventRecord | None = None,
    detail_type: str = "workout",
    **kwargs,
) -> EventRecordDetail:
    """Create a test event record detail."""
    if event_record is None:
        event_record = create_event_record(db)

    detail = EventRecordDetail(
        record_id=event_record.id,
        detail_type=detail_type,
    )
    db.add(detail)
    db.commit()
    db.refresh(detail)
    return detail


def create_data_point_series(
    db: Session,
    *,
    mapping: ExternalDeviceMapping | None = None,
    series_type: SeriesTypeDefinition | None = None,
    value: float = 72.0,
    recorded_at: datetime | None = None,
    **kwargs,
) -> DataPointSeries:
    """Create a test data point series entry."""
    from decimal import Decimal

    if mapping is None:
        mapping = create_external_device_mapping(db)

    if series_type is None:
        series_type = create_series_type_definition(db, code="heart_rate", unit="bpm")

    data_point = DataPointSeries(
        id=kwargs.get("id", uuid4()),
        external_mapping_id=mapping.id,
        series_type_id=series_type.id,
        value=Decimal(str(value)),
        recorded_at=recorded_at or datetime.now(timezone.utc),
    )
    db.add(data_point)
    db.commit()
    db.refresh(data_point)
    return data_point


def create_provider_setting(
    db: Session,
    *,
    provider: str = "garmin",
    is_enabled: bool = True,
    **kwargs,
) -> ProviderSetting:
    """Create a test provider setting."""
    # Check if it already exists
    existing = db.query(ProviderSetting).filter(ProviderSetting.provider == provider).first()
    if existing:
        existing.is_enabled = is_enabled
        db.commit()
        db.refresh(existing)
        return existing

    setting = ProviderSetting(
        provider=provider,
        is_enabled=is_enabled,
    )
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


def create_workout_details(
    db: Session,
    *,
    event_record: EventRecord | None = None,
    heart_rate_avg: Decimal | None = None,
    heart_rate_max: int | None = None,
    heart_rate_min: int | None = None,
    steps_total: int | None = None,
    **kwargs,
) -> WorkoutDetails:
    """Create a test workout details record."""
    from decimal import Decimal as Dec

    if event_record is None:
        event_record = create_event_record(db, category="workout")

    details = WorkoutDetails(
        record_id=event_record.id,
        heart_rate_avg=heart_rate_avg or Dec("145.5"),
        heart_rate_max=heart_rate_max or 175,
        heart_rate_min=heart_rate_min or 95,
        steps_total=steps_total or 8500,
        **kwargs,
    )
    db.add(details)
    db.commit()
    db.refresh(details)
    return details


def create_sleep_details(
    db: Session,
    *,
    event_record: EventRecord | None = None,
    sleep_total_duration_minutes: int | None = None,
    sleep_deep_minutes: int | None = None,
    sleep_light_minutes: int | None = None,
    sleep_rem_minutes: int | None = None,
    sleep_awake_minutes: int | None = None,
    **kwargs,
) -> SleepDetails:
    """Create a test sleep details record."""
    if event_record is None:
        event_record = create_event_record(db, category="sleep", type_="sleep")

    details = SleepDetails(
        record_id=event_record.id,
        sleep_total_duration_minutes=sleep_total_duration_minutes or 480,  # 8 hours
        sleep_deep_minutes=sleep_deep_minutes or 120,  # 2 hours
        sleep_light_minutes=sleep_light_minutes or 240,  # 4 hours
        sleep_rem_minutes=sleep_rem_minutes or 90,  # 1.5 hours
        sleep_awake_minutes=sleep_awake_minutes or 30,  # 30 min
        **kwargs,
    )
    db.add(details)
    db.commit()
    db.refresh(details)
    return details
