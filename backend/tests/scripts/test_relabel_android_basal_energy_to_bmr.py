"""Tests for the data migration that relabels Android basal_energy -> basal_metabolic_rate.

Health Connect's BasalMetabolicRateRecord (and the Samsung equivalent) is a kcal/day
rate, but ingestion historically stored it under basal_energy (id=82). On the Android
SDK providers no other record writes basal_energy, so every health_connect/samsung
row is a BMR reading. See scripts/data_migrations/relabel_android_basal_energy_to_bmr.py.
"""

import importlib.util
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import DataPointSeriesArchive, SeriesSample, SeriesTypeDefinition
from app.schemas.enums.aggregation_method import AggregationMethod
from app.schemas.enums.provider import ProviderName
from tests.factories import DataPointSeriesFactory, DataSourceFactory

BASAL_ENERGY_ID = 82
BMR_ID = 90

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "relabel_android_basal_energy_to_bmr.py"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("relabel_android_basal_energy_to_bmr", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


relabel_android_basal_energy = _load_module().relabel_android_basal_energy


def _series_type(db: Session, type_id: int) -> SeriesTypeDefinition:
    """Fetch a series type seeded at session scope (see conftest.engine)."""
    return db.get(SeriesTypeDefinition, type_id)


def _make_point(
    db: Session, *, provider: ProviderName, type_id: int, recorded_at: datetime, value: str
) -> SeriesSample:
    source = DataSourceFactory(provider=provider)
    return DataPointSeriesFactory(
        data_source=source,
        series_type=_series_type(db, type_id),
        recorded_at=recorded_at,
        value=Decimal(value),
    )


def _make_archive_row(
    db: Session,
    *,
    provider: ProviderName,
    type_id: int,
    bucket_start_at: datetime,
    aggregation: AggregationMethod = AggregationMethod.AVG,
    value: str = "1520",
    sample_count: int = 10,
) -> None:
    source = DataSourceFactory(provider=provider)
    db.add(
        DataPointSeriesArchive(
            id=uuid4(),
            data_source_id=source.id,
            series_type_definition_id=type_id,
            bucket_start_at=bucket_start_at,
            aggregation_type=aggregation,
            value=Decimal(value),
            sample_count=sample_count,
        )
    )
    db.flush()


def _type_ids(db: Session, table: str) -> list[int]:
    rows = db.execute(text(f"SELECT series_type_definition_id FROM {table}")).scalars().all()
    return list(rows)


def _insert_coverage(db: Session, *, source: object, data_type: str, start: str, end: str) -> None:
    db.execute(
        text(
            "INSERT INTO data_type_coverage"
            " (user_id, provider, data_type, kind, coverage_start, coverage_end, last_written_at)"
            " VALUES (:user_id, :provider, :data_type, 'series', :start, :end, :end)"
        ),
        {
            "user_id": source.user_id,
            "provider": source.provider,
            "data_type": data_type,
            "start": datetime.fromisoformat(start).replace(tzinfo=timezone.utc),
            "end": datetime.fromisoformat(end).replace(tzinfo=timezone.utc),
        },
    )


T = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)


def test_relabels_health_connect_basal_energy_to_bmr(db: Session) -> None:
    _make_point(db, provider=ProviderName.HEALTH_CONNECT, type_id=BASAL_ENERGY_ID, recorded_at=T, value="1520")
    _make_point(db, provider=ProviderName.SAMSUNG, type_id=BASAL_ENERGY_ID, recorded_at=T, value="1480")

    result = relabel_android_basal_energy(db, dry_run=False)

    assert result["series_updated"] == 2
    assert _type_ids(db, "series_sample") == [BMR_ID, BMR_ID]


def test_relabel_clears_the_daily_total_flag(db: Session) -> None:
    """BMR readings are instantaneous rates; the AVG series carries is_daily_total=NULL."""
    point = _make_point(db, provider=ProviderName.HEALTH_CONNECT, type_id=BASAL_ENERGY_ID, recorded_at=T, value="1520")
    point.is_daily_total = False
    db.flush()

    relabel_android_basal_energy(db, dry_run=False)

    flag = db.execute(text("SELECT is_daily_total FROM series_sample")).scalar_one()
    assert flag is None


def test_leaves_apple_and_oauth_provider_basal_energy_untouched(db: Session) -> None:
    # Apple's basal energy is genuine interval energy (HKQuantityTypeIdentifierBasalEnergyBurned).
    _make_point(db, provider=ProviderName.APPLE, type_id=BASAL_ENERGY_ID, recorded_at=T, value="1850")
    _make_point(db, provider=ProviderName.GARMIN, type_id=BASAL_ENERGY_ID, recorded_at=T, value="1700")
    _make_point(db, provider=ProviderName.HEALTH_CONNECT, type_id=BASAL_ENERGY_ID, recorded_at=T, value="1520")

    result = relabel_android_basal_energy(db, dry_run=False)

    assert result["series_updated"] == 1
    assert sorted(_type_ids(db, "series_sample")) == [BASAL_ENERGY_ID, BASAL_ENERGY_ID, BMR_ID]


def test_drops_basal_row_already_synced_as_bmr(db: Session) -> None:
    source = DataSourceFactory(provider=ProviderName.HEALTH_CONNECT)
    for type_id, value in ((BASAL_ENERGY_ID, "1520"), (BMR_ID, "1525")):
        DataPointSeriesFactory(
            data_source=source, series_type=_series_type(db, type_id), recorded_at=T, value=Decimal(value)
        )

    result = relabel_android_basal_energy(db, dry_run=False)

    assert (result["series_updated"], result["series_deleted"]) == (0, 1)
    rows = db.execute(text("SELECT series_type_definition_id, value FROM series_sample")).tuples().all()
    assert rows == [(BMR_ID, Decimal("1525"))]


def test_relabels_archive_rows(db: Session) -> None:
    _make_archive_row(db, provider=ProviderName.HEALTH_CONNECT, type_id=BASAL_ENERGY_ID, bucket_start_at=T)
    _make_archive_row(db, provider=ProviderName.APPLE, type_id=BASAL_ENERGY_ID, bucket_start_at=T)

    result = relabel_android_basal_energy(db, dry_run=False)

    assert result["archive_updated"] == 1
    assert sorted(_type_ids(db, "data_point_series_archive")) == [BASAL_ENERGY_ID, BMR_ID]


def test_sum_archive_rows_become_avg_rows(db: Session) -> None:
    """basal_energy archives are sums of rate samples; the AVG series needs the mean, sum/count."""
    _make_archive_row(
        db,
        provider=ProviderName.HEALTH_CONNECT,
        type_id=BASAL_ENERGY_ID,
        bucket_start_at=T,
        aggregation=AggregationMethod.SUM,
        value="3040",
        sample_count=2,
    )

    relabel_android_basal_energy(db, dry_run=False)

    rows = (
        db.execute(text("SELECT series_type_definition_id, aggregation_type, value FROM data_point_series_archive"))
        .tuples()
        .all()
    )
    assert rows == [(BMR_ID, "avg", Decimal("1520.000"))]


def test_sum_archive_row_colliding_with_a_resynced_avg_is_dropped(db: Session) -> None:
    source = DataSourceFactory(provider=ProviderName.HEALTH_CONNECT)
    for type_id, aggregation, value in (
        (BASAL_ENERGY_ID, AggregationMethod.SUM, "3040"),
        (BMR_ID, AggregationMethod.AVG, "1525"),
    ):
        db.add(
            DataPointSeriesArchive(
                id=uuid4(),
                data_source_id=source.id,
                series_type_definition_id=type_id,
                bucket_start_at=T,
                aggregation_type=aggregation,
                value=Decimal(value),
                sample_count=2,
            )
        )
    db.flush()

    result = relabel_android_basal_energy(db, dry_run=False)

    assert (result["archive_updated"], result["archive_deleted"]) == (0, 1)
    rows = (
        db.execute(text("SELECT series_type_definition_id, aggregation_type, value FROM data_point_series_archive"))
        .tuples()
        .all()
    )
    assert rows == [(BMR_ID, "avg", Decimal("1525"))]


def test_coverage_rekeys_to_basal_metabolic_rate(db: Session) -> None:
    source = DataSourceFactory(provider=ProviderName.HEALTH_CONNECT)
    _insert_coverage(db, source=source, data_type="basal_energy", start="2025-01-01", end="2025-06-01")
    _insert_coverage(db, source=source, data_type="basal_metabolic_rate", start="2025-03-01", end="2025-09-01")
    apple = DataSourceFactory(provider=ProviderName.APPLE)
    _insert_coverage(db, source=apple, data_type="basal_energy", start="2025-01-01", end="2025-02-01")

    relabel_android_basal_energy(db, dry_run=False)

    rows = sorted(
        db.execute(text("SELECT provider, data_type, coverage_start, coverage_end FROM data_type_coverage"))
        .tuples()
        .all()
    )
    assert rows == [
        (
            "apple",
            "basal_energy",
            datetime(2025, 1, 1, tzinfo=timezone.utc),
            datetime(2025, 2, 1, tzinfo=timezone.utc),
        ),
        (
            "health_connect",
            "basal_metabolic_rate",
            datetime(2025, 1, 1, tzinfo=timezone.utc),
            datetime(2025, 9, 1, tzinfo=timezone.utc),
        ),
    ]


def test_coverage_rekeys_without_a_conflict(db: Session) -> None:
    source = DataSourceFactory(provider=ProviderName.SAMSUNG)
    _insert_coverage(db, source=source, data_type="basal_energy", start="2025-01-01", end="2025-06-01")

    relabel_android_basal_energy(db, dry_run=False)

    rows = db.execute(text("SELECT data_type FROM data_type_coverage")).scalars().all()
    assert rows == ["basal_metabolic_rate"]


def test_dry_run_makes_no_changes(db: Session) -> None:
    _make_point(db, provider=ProviderName.HEALTH_CONNECT, type_id=BASAL_ENERGY_ID, recorded_at=T, value="1520")

    result = relabel_android_basal_energy(db, dry_run=True)

    assert result["series_updated"] == 1  # reported as "would update"
    assert _type_ids(db, "series_sample") == [BASAL_ENERGY_ID]


def test_idempotent_second_run_is_noop(db: Session) -> None:
    _make_point(
        db,
        provider=ProviderName.HEALTH_CONNECT,
        type_id=BASAL_ENERGY_ID,
        recorded_at=T + timedelta(hours=1),
        value="1520",
    )

    relabel_android_basal_energy(db, dry_run=False)
    second = relabel_android_basal_energy(db, dry_run=False)

    assert second["series_updated"] == 0
    assert second["series_deleted"] == 0
    assert _type_ids(db, "series_sample") == [BMR_ID]
