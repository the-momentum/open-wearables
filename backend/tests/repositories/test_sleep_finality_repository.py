"""Whether a sleep session's source sent data from a given moment on."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import SeriesAggregate
from app.repositories.sleep_finality_repository import sleep_finality_repository
from app.schemas.enums import ComputedBy, PeriodKind
from tests.factories import DataPointSeriesFactory, DataSourceFactory, SeriesTypeDefinitionFactory


def test_sessions_whose_source_sent_data_from_their_moment_on(db: Session) -> None:
    heart_rate = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
    steps = SeriesTypeDefinitionFactory.get_or_create_steps()
    since = datetime(2026, 10, 31, 8, 0, tzinfo=timezone.utc)
    too_early, on_time, day_row, elsewhere = (DataSourceFactory() for _ in range(4))
    DataPointSeriesFactory(data_source=too_early, series_type=heart_rate, recorded_at=since - timedelta(minutes=1))
    DataPointSeriesFactory(data_source=on_time, series_type=heart_rate, recorded_at=since)
    # A provider that sends daily totals only: the next day's steps row
    db.add(
        SeriesAggregate(
            id=uuid4(),
            data_source_id=day_row.id,
            series_type_definition_id=steps.id,
            period_kind=PeriodKind.DAY,
            period_start=since,
            period_end=since + timedelta(days=1),
            zone_offset="+00:00",
            computed_by=ComputedBy.PROVIDER,
            sum=Decimal(500),
            count=1,
        )
    )
    DataPointSeriesFactory(data_source=elsewhere, series_type=heart_rate, recorded_at=since + timedelta(hours=1))
    db.flush()
    sessions = {source.id: uuid4() for source in (too_early, on_time, day_row)}

    found = sleep_finality_repository.with_data_since(
        db, [(record, source, since) for source, record in sessions.items()]
    )

    assert found == {sessions[on_time.id], sessions[day_row.id]}


def test_no_sessions_no_query(db: Session) -> None:
    assert sleep_finality_repository.with_data_since(db, []) == set()
