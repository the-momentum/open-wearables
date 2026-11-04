"""Whether a sleep session's provider sent data from a given moment on."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import SeriesAggregate
from app.repositories.sleep_finality_repository import sleep_finality_repository
from app.schemas.enums import ComputedBy, PeriodKind, ProviderName
from tests.factories import DataPointSeriesFactory, DataSourceFactory, SeriesTypeDefinitionFactory, UserFactory

SINCE = datetime(2026, 10, 31, 8, 0, tzinfo=timezone.utc)


def test_sessions_with_data_since_the_given_moment(db: Session) -> None:
    heart_rate = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
    steps = SeriesTypeDefinitionFactory.get_or_create_steps()
    too_early, on_time, day_row, elsewhere = (DataSourceFactory() for _ in range(4))
    DataPointSeriesFactory(data_source=too_early, series_type=heart_rate, recorded_at=SINCE - timedelta(minutes=1))
    DataPointSeriesFactory(data_source=on_time, series_type=heart_rate, recorded_at=SINCE)
    # A provider that sends daily totals only: the next day's steps row
    db.add(
        SeriesAggregate(
            id=uuid4(),
            data_source_id=day_row.id,
            series_type_definition_id=steps.id,
            period_kind=PeriodKind.DAY,
            period_start=SINCE,
            period_end=SINCE + timedelta(days=1),
            zone_offset="+00:00",
            computed_by=ComputedBy.PROVIDER,
            sum=Decimal(500),
            count=1,
        )
    )
    DataPointSeriesFactory(data_source=elsewhere, series_type=heart_rate, recorded_at=SINCE + timedelta(hours=1))
    db.flush()
    sessions = {source.id: uuid4() for source in (too_early, on_time, day_row)}

    found = sleep_finality_repository.with_data_since(
        db, [(record, source, SINCE) for source, record in sessions.items()]
    )

    assert found == {sessions[on_time.id], sessions[day_row.id]}


def test_data_from_another_of_the_users_sources_at_the_provider_counts(db: Session) -> None:
    """Polar files a night under the watch's device id and its heart rate and steps under a source without one."""
    heart_rate = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
    polar_user, oura_user = UserFactory(), UserFactory()
    polar_night = DataSourceFactory(user=polar_user, provider=ProviderName.POLAR, device_id="A1B2C3D4")
    oura_night = DataSourceFactory(user=oura_user, provider=ProviderName.OURA)
    for source in (
        DataSourceFactory(user=polar_user, provider=ProviderName.POLAR),
        DataSourceFactory(user=oura_user, provider=ProviderName.SUUNTO),
        DataSourceFactory(provider=ProviderName.OURA),
    ):
        DataPointSeriesFactory(data_source=source, series_type=heart_rate, recorded_at=SINCE)
    db.flush()
    polar_record, oura_record = uuid4(), uuid4()

    found = sleep_finality_repository.with_data_since(
        db, [(polar_record, polar_night.id, SINCE), (oura_record, oura_night.id, SINCE)]
    )

    assert found == {polar_record}


def test_no_sessions_no_query(db: Session) -> None:
    assert sleep_finality_repository.with_data_since(db, []) == set()
