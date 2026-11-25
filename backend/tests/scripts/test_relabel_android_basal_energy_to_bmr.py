"""Tests for the data migration that relabels Android basal_energy -> basal_metabolic_rate.

Health Connect's BasalMetabolicRateRecord (and the Samsung equivalent) is a kcal/day
rate, but ingestion historically stored it under basal_energy (id=82). On the Android
SDK providers no other record writes basal_energy, so every health_connect/samsung
row is a BMR reading. See scripts/data_migrations/relabel_android_basal_energy_to_bmr.py.
"""

import importlib.util
import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import DataPointSeriesArchive, DataSource, SeriesSample, SeriesTypeDefinition, User
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


_module = _load_module()
relabel_android_basal_energy = _module.relabel_android_basal_energy
_relabel_rows = _module._relabel_rows
_rekey_coverage = _module._rekey_coverage


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


def test_rolling_deploy_write_converges_on_the_next_run(db: Session) -> None:
    """A pod on the previous release keeps writing basal_energy until the rollout ends. Its row
    and the coverage the write path recreates are both moved once a later run sees them."""
    source = DataSourceFactory(provider=ProviderName.HEALTH_CONNECT)
    relabel_android_basal_energy(db, dry_run=False)

    late = DataPointSeriesFactory(
        data_source=source,
        series_type=_series_type(db, BASAL_ENERGY_ID),
        recorded_at=T,
        value=Decimal("1500"),
    )
    db.flush()
    _insert_coverage(db, source=source, data_type="basal_energy", start="2026-01-01", end="2026-01-01")

    relabel_android_basal_energy(db, dry_run=False)

    assert db.execute(text("SELECT series_type_definition_id FROM series_sample")).scalars().all() == [BMR_ID]
    rows = db.execute(text("SELECT data_type FROM data_type_coverage")).scalars().all()
    assert rows == ["basal_metabolic_rate"]
    assert late.id is not None


def test_interleaved_rolling_deploy_write_keeps_coverage_for_both_series(db: Session) -> None:
    """The race itself, in order: rows relabeled, then a pod on the previous release commits
    a basal_energy write before the coverage statements run. The re-key must still move the
    original span to basal_metabolic_rate (the moved rows are most of the data), and the
    repair must leave a basal_energy key narrowed to exactly the straggler."""
    source = DataSourceFactory(provider=ProviderName.HEALTH_CONNECT)
    DataPointSeriesFactory(
        data_source=source,
        series_type=_series_type(db, BASAL_ENERGY_ID),
        recorded_at=T,
        value=Decimal("1500"),
    )
    db.flush()
    _insert_coverage(db, source=source, data_type="basal_energy", start="2026-01-01", end="2026-01-01")

    series_updated, _, _, _ = _relabel_rows(db)
    assert series_updated == 1

    late_at = T + timedelta(hours=5)
    DataPointSeriesFactory(
        data_source=source,
        series_type=_series_type(db, BASAL_ENERGY_ID),
        recorded_at=late_at,
        value=Decimal("1510"),
    )
    db.flush()
    # the write path widens basal_energy coverage for the late write before the migration's
    # coverage statements run — the re-key then carries that width over to the BMR key.
    # the straggler syncs a sample recorded days before it arrives, as a real pod would
    writer_arrival = late_at + timedelta(days=2)
    db.execute(
        text("UPDATE data_type_coverage SET coverage_end = :late, last_written_at = :arrival"),
        {"late": late_at, "arrival": writer_arrival},
    )

    _, repaired = _rekey_coverage(db)

    rows = {
        row.data_type: row
        for row in db.execute(
            text("SELECT data_type, coverage_start, coverage_end, last_written_at FROM data_type_coverage")
        )
    }
    assert set(rows) == {"basal_metabolic_rate", "basal_energy"}
    # the straggler keeps a basal_energy span narrowed to itself
    assert rows["basal_energy"].coverage_start == late_at
    assert rows["basal_energy"].coverage_end == late_at
    # last_written_at preserves the writer's arrival time captured before the re-key,
    # not the sample time and never the repair time
    assert rows["basal_energy"].last_written_at == writer_arrival
    # the BMR span is recomputed from the rows actually held and does not reach the straggler
    assert rows["basal_metabolic_rate"].coverage_start == T
    assert rows["basal_metabolic_rate"].coverage_end == T
    assert repaired == 1


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


def test_concurrent_bmr_writer_is_not_overwritten(session_factory: Any) -> None:
    """Two sessions, real concurrency: a pod already on the new release writes BMR rows and
    widens coverage while the migration re-keys. Whatever the interleaving, the final
    basal_metabolic_rate span must exactly envelope the rows held — the recompute must never
    overwrite a wider span written from rows its snapshot did not include."""
    setup = session_factory()
    user = User(id=uuid4(), email=f"concurrent-{uuid4().hex[:8]}@example.com", first_name="C", last_name="T")
    setup.add(user)
    setup.flush()
    source = DataSource(
        id=uuid4(),
        user_id=user.id,
        provider=ProviderName.HEALTH_CONNECT,
        device_model=f"dev-{uuid4().hex[:8]}",
        software_version="1.0.0",
        source="health_connect",
        device_type="phone",
    )
    setup.add(source)
    setup.flush()
    setup.add(
        SeriesSample(
            id=uuid4(),
            data_source_id=source.id,
            series_type_definition_id=BASAL_ENERGY_ID,
            recorded_at=T,
            value=Decimal("1500"),
        )
    )
    setup.execute(
        text(
            "INSERT INTO data_type_coverage"
            " (user_id, provider, data_type, kind, coverage_start, coverage_end, last_written_at)"
            " VALUES (:uid, :prov, 'basal_energy', 'series', :t, :t, :t)"
        ),
        {"uid": user.id, "prov": ProviderName.HEALTH_CONNECT, "t": T},
    )
    user_id, source_id = user.id, source.id
    setup.commit()
    setup.close()

    writer_errors: list[Exception] = []

    def write_bmr_rows() -> None:
        try:
            for i in range(6):
                w = session_factory()
                at = T + timedelta(hours=1, minutes=i)
                w.add(
                    SeriesSample(
                        id=uuid4(),
                        data_source_id=source_id,
                        series_type_definition_id=BMR_ID,
                        recorded_at=at,
                        value=Decimal("1520"),
                    )
                )
                w.execute(
                    text(
                        "INSERT INTO data_type_coverage"
                        " (user_id, provider, data_type, kind, coverage_start, coverage_end, last_written_at)"
                        " VALUES (:uid, :prov, 'basal_metabolic_rate', 'series', :t, :t, :t)"
                        " ON CONFLICT (user_id, provider, data_type, kind) DO UPDATE SET"
                        " coverage_start = LEAST(EXCLUDED.coverage_start, data_type_coverage.coverage_start),"
                        " coverage_end = GREATEST(EXCLUDED.coverage_end, data_type_coverage.coverage_end),"
                        " last_written_at = GREATEST(EXCLUDED.last_written_at, data_type_coverage.last_written_at)"
                    ),
                    {"uid": user_id, "prov": ProviderName.HEALTH_CONNECT, "t": at},
                )
                w.commit()
                w.close()
                time.sleep(0.05)
        except Exception as exc:  # noqa: BLE001 - surfaced in the assertion below
            writer_errors.append(exc)

    writer = threading.Thread(target=write_bmr_rows)
    writer.start()

    migration_errors: list[Exception] = []
    migration_done = False

    def run_migration() -> None:
        nonlocal migration_done
        for _attempt in range(3):
            m = session_factory()
            try:
                relabel_android_basal_energy(m, dry_run=False)
                m.commit()
                m.close()
                migration_done = True
                return
            except Exception as exc:  # noqa: BLE001 - a deadlock loser retries, like the next startup would
                m.rollback()
                m.close()
                migration_errors.append(exc)

    try:
        run_migration()
        writer.join(timeout=30)

        assert migration_done, f"migration failed every attempt: {migration_errors}"
        assert not writer_errors, f"writer failed: {writer_errors}"

        check = session_factory()
        rows = check.execute(
            text(
                "SELECT coverage_start, coverage_end FROM data_type_coverage"
                " WHERE user_id = :uid AND data_type = 'basal_metabolic_rate'"
            ),
            {"uid": user_id},
        ).all()
        held = check.execute(
            text(
                "SELECT MIN(recorded_at), MAX(recorded_at) FROM series_sample"
                " WHERE data_source_id = :dsid AND series_type_definition_id = :bmr"
            ),
            {"dsid": source_id, "bmr": BMR_ID},
        ).one()
        assert len(rows) == 1
        assert rows[0].coverage_start == held[0]
        assert rows[0].coverage_end == held[1]
        check.close()
    finally:
        cleanup = session_factory()
        cleanup.execute(text("DELETE FROM series_sample WHERE data_source_id = :dsid"), {"dsid": source_id})
        cleanup.execute(text("DELETE FROM data_type_coverage WHERE user_id = :uid"), {"uid": user_id})
        cleanup.execute(text("DELETE FROM data_source WHERE id = :dsid"), {"dsid": source_id})
        cleanup.execute(text('DELETE FROM "user" WHERE id = :uid'), {"uid": user_id})
        cleanup.commit()
        cleanup.close()


def test_repair_preserves_a_surviving_writers_arrival_time(db: Session) -> None:
    """When the straggler's own coverage write lands after the re-key, its row survives and
    the repair only widens it: the writer's arrival time is always >= the sample time, so
    GREATEST keeps it instead of the approximation."""
    source = DataSourceFactory(provider=ProviderName.HEALTH_CONNECT)
    straggler_at = T
    writer_arrival = T + timedelta(hours=2)
    DataPointSeriesFactory(
        data_source=source,
        series_type=_series_type(db, BASAL_ENERGY_ID),
        recorded_at=straggler_at,
        value=Decimal("1500"),
    )
    db.flush()
    db.execute(
        text(
            "INSERT INTO data_type_coverage"
            " (user_id, provider, data_type, kind, coverage_start, coverage_end, last_written_at)"
            " VALUES (:uid, :prov, 'basal_energy', 'series', :t, :t, :arrival)"
        ),
        {"uid": source.user_id, "prov": source.provider, "t": straggler_at, "arrival": writer_arrival},
    )

    for statement in _module._COVERAGE_CAPTURE:
        db.execute(statement, _module._PARAMS)
    db.execute(_module._COVERAGE_REPAIR, _module._PARAMS)

    row = db.execute(text("SELECT coverage_start, coverage_end, last_written_at FROM data_type_coverage")).one()
    assert row.coverage_start == straggler_at
    assert row.coverage_end == straggler_at
    assert row.last_written_at == writer_arrival


def test_key_inserted_mid_migration_keeps_its_arrival_time(session_factory: Any) -> None:
    """Round-7 interleaving with two committed sessions: the migration transaction has
    already relabeled the rows when an old pod inserts a brand-new basal_energy coverage
    key — nothing existed to lock or snapshot when the migration started. READ COMMITTED
    means the re-key still sees it, so the capture must happen in the moving statement
    itself, and the repair must hand the genuine arrival time to the replacement key."""
    setup = session_factory()
    user = User(id=uuid4(), email=f"midkey-{uuid4().hex[:8]}@example.com", first_name="M", last_name="K")
    setup.add(user)
    setup.flush()
    source = DataSource(
        id=uuid4(),
        user_id=user.id,
        provider=ProviderName.HEALTH_CONNECT,
        device_model=f"dev-{uuid4().hex[:8]}",
        software_version="1.0.0",
        source="health_connect",
        device_type="phone",
    )
    setup.add(source)
    setup.flush()
    user_id, source_id = user.id, source.id
    setup.commit()
    setup.close()

    migration = session_factory()
    writer = session_factory()
    try:
        # nothing to relabel yet — the basal row only arrives with the writer
        _relabel_rows(migration)

        sample_at = T - timedelta(days=4)
        arrival = T + timedelta(hours=3)
        writer.add(
            SeriesSample(
                id=uuid4(),
                data_source_id=source_id,
                series_type_definition_id=BASAL_ENERGY_ID,
                recorded_at=sample_at,
                value=Decimal("1500"),
            )
        )
        writer.execute(
            text(
                "INSERT INTO data_type_coverage"
                " (user_id, provider, data_type, kind, coverage_start, coverage_end, last_written_at)"
                " VALUES (:uid, :prov, 'basal_energy', 'series', :t, :t, :arrival)"
            ),
            {"uid": user_id, "prov": ProviderName.HEALTH_CONNECT, "t": sample_at, "arrival": arrival},
        )
        writer.commit()

        _rekey_coverage(migration)
        migration.commit()

        rows = {
            row.data_type: row
            for row in migration.execute(
                text("SELECT data_type, coverage_start, coverage_end, last_written_at FROM data_type_coverage")
            )
        }
        assert set(rows) == {"basal_metabolic_rate", "basal_energy"}
        assert rows["basal_energy"].coverage_start == sample_at
        assert rows["basal_energy"].coverage_end == sample_at
        # the key did not exist when the migration started, yet its genuine arrival
        # time survives — captured in the statement that moved it
        assert rows["basal_energy"].last_written_at == arrival
    finally:
        for s in (migration, writer):
            s.rollback()
            s.close()
        cleanup = session_factory()
        cleanup.execute(text("DELETE FROM series_sample WHERE data_source_id = :dsid"), {"dsid": source_id})
        cleanup.execute(text("DELETE FROM data_type_coverage WHERE user_id = :uid"), {"uid": user_id})
        cleanup.execute(text("DELETE FROM data_source WHERE id = :dsid"), {"dsid": source_id})
        cleanup.execute(text('DELETE FROM "user" WHERE id = :uid'), {"uid": user_id})
        cleanup.commit()
        cleanup.close()


def test_key_inserted_between_delete_and_rename_does_not_abort(session_factory: Any) -> None:
    """The round-8 ordering, two committed sessions: a basal_metabolic_rate key exists, the
    migration passes its delete statement, and only then does the old pod commit a fresh
    basal_energy key for the same user. Renaming it would violate the coverage primary key
    and roll the migration back — instead it must stay in place as accurate coverage for
    the straggler row that arrived with it."""
    setup = session_factory()
    user = User(id=uuid4(), email=f"collision-{uuid4().hex[:8]}@example.com", first_name="C", last_name="K")
    setup.add(user)
    setup.flush()
    source = DataSource(
        id=uuid4(),
        user_id=user.id,
        provider=ProviderName.HEALTH_CONNECT,
        device_model=f"dev-{uuid4().hex[:8]}",
        software_version="1.0.0",
        source="health_connect",
        device_type="phone",
    )
    setup.add(source)
    setup.flush()
    user_id, source_id = user.id, source.id
    # a basal_metabolic_rate coverage key already exists for this user — the collision target
    setup.execute(
        text(
            "INSERT INTO data_type_coverage"
            " (user_id, provider, data_type, kind, coverage_start, coverage_end, last_written_at)"
            " VALUES (:uid, :prov, 'basal_metabolic_rate', 'series', :t, :t, :t)"
        ),
        {"uid": user_id, "prov": ProviderName.HEALTH_CONNECT, "t": T},
    )
    setup.commit()
    setup.close()

    migration = session_factory()
    writer = session_factory()
    try:
        # migration: lock, capture table, merge and delete statements — the writer's key
        # does not exist yet, so none of this touches it
        migration.execute(_module._COVERAGE_ADVISORY_LOCK)
        migration.execute(_module._COVERAGE_ROW_LOCK, _module._PARAMS)
        for statement in _module._COVERAGE_CAPTURE:
            migration.execute(statement, _module._PARAMS)
        migration.execute(_module._COVERAGE_MOVE[0], _module._PARAMS)

        # the old pod commits row and coverage key atomically, between delete and rename
        sample_at = T - timedelta(days=2)
        arrival = T + timedelta(hours=1)
        writer.add(
            SeriesSample(
                id=uuid4(),
                data_source_id=source_id,
                series_type_definition_id=BASAL_ENERGY_ID,
                recorded_at=sample_at,
                value=Decimal("1500"),
            )
        )
        writer.execute(
            text(
                "INSERT INTO data_type_coverage"
                " (user_id, provider, data_type, kind, coverage_start, coverage_end, last_written_at)"
                " VALUES (:uid, :prov, 'basal_energy', 'series', :t, :t, :arrival)"
            ),
            {"uid": user_id, "prov": ProviderName.HEALTH_CONNECT, "t": sample_at, "arrival": arrival},
        )
        writer.commit()

        # the delete captures the late key's arrival time; repair and recompute complete
        migration.execute(_module._COVERAGE_MOVE[1], _module._PARAMS)
        migration.execute(_module._COVERAGE_REPAIR, _module._PARAMS)
        migration.execute(_module._BMR_SPAN_RECOMPUTE, _module._PARAMS)
        migration.commit()

        rows = {
            row.data_type: row
            for row in migration.execute(
                text("SELECT data_type, coverage_start, coverage_end, last_written_at FROM data_type_coverage")
            )
        }
        assert set(rows) == {"basal_metabolic_rate", "basal_energy"}
        # the colliding key stays in place as accurate coverage for the straggler row
        assert rows["basal_energy"].coverage_start == sample_at
        assert rows["basal_energy"].coverage_end == sample_at
        assert rows["basal_energy"].last_written_at == arrival
    finally:
        for s in (migration, writer):
            s.rollback()
            s.close()
        cleanup = session_factory()
        cleanup.execute(text("DELETE FROM series_sample WHERE data_source_id = :dsid"), {"dsid": source_id})
        cleanup.execute(text("DELETE FROM data_type_coverage WHERE user_id = :uid"), {"uid": user_id})
        cleanup.execute(text("DELETE FROM data_source WHERE id = :dsid"), {"dsid": source_id})
        cleanup.execute(text('DELETE FROM "user" WHERE id = :uid'), {"uid": user_id})
        cleanup.commit()
        cleanup.close()
