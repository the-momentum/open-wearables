"""source_selection=reconcile: a summed series merged across a user's sources per day, stored by the rollup within
its own budget for recent days, merged on the fly by reads up to a limit."""

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.config import settings
from app.integrations.rollup_queue import pop_reconcile_days, queue_reconcile_days, requeue_dirty_days
from app.models import DataSource, ProviderPriority, SeriesTypeDefinition
from app.models.archival_setting import ArchivalSetting
from app.repositories import ProviderPriorityRepository
from app.repositories.data_migration_repository import DataMigrationRepository
from app.repositories.data_source_repository import DataSourceRepository
from app.repositories.series_reconcile_repository import RECONCILED_SERIES, SeriesReconcileRepository
from app.repositories.series_rollup_repository import SeriesRollupRepository
from app.schemas.enums import (
    AGGREGATION_METHOD_BY_TYPE,
    AggregationMethod,
    ProviderName,
    Resolution,
    SeriesType,
    SourceSelection,
    get_series_type_id,
)
from app.schemas.model_crud.activities import TimeSeriesQueryParams
from app.services.archival_service import archival_service
from app.services.priority_service import priority_service
from app.services.timeseries_service import timeseries_service
from tests.factories import (
    ApiKeyFactory,
    DataPointSeriesFactory,
    DataSourceFactory,
    SeriesTypeDefinitionFactory,
    UserFactory,
)

DAY = date(2024, 3, 2)
STEPS = get_series_type_id(SeriesType.steps)


def _steps(source: DataSource, day: date, hour: int, value: int, seconds: int = 60) -> None:
    DataPointSeriesFactory(
        mapping=source,
        series_type=SeriesTypeDefinitionFactory.get_or_create_steps(),
        recorded_at=datetime.combine(day, datetime.min.time(), timezone.utc) + timedelta(hours=hour),
        window_seconds=seconds,
        value=value,
    )


@pytest.fixture
def devices(db: Session) -> tuple[DataSource, DataSource]:
    """A watch ranked before a phone."""
    user = UserFactory()
    watch = DataSourceFactory(user=user, provider=ProviderName.GARMIN, source="garmin", device_type="watch")
    phone = DataSourceFactory(user=user, provider=ProviderName.APPLE, source="apple_health_sdk", device_type="phone")
    priorities = ProviderPriorityRepository(ProviderPriority)
    priorities.upsert(db, ProviderName.GARMIN, 1)
    priorities.upsert(db, ProviderName.APPLE, 2)
    return watch, phone


def _walk(watch: DataSource, phone: DataSource, day: date) -> None:
    """The watch counts 150; the phone counts 90 the watch also covers and 30 while the watch was off: 180."""
    _steps(watch, day, 9, 100)
    _steps(watch, day, 10, 50)
    _steps(phone, day, 9, 90)
    _steps(phone, day, 12, 30)


def _read(db: Session, source: DataSource, first: date, last: date, **params: object) -> list[tuple]:
    query = TimeSeriesQueryParams(
        start_datetime=datetime.combine(first, datetime.min.time(), timezone.utc),
        end_datetime=datetime.combine(last + timedelta(days=1), datetime.min.time(), timezone.utc),
        resolution=Resolution.ONE_DAY,
        **params,
    )
    result = timeseries_service.get_timeseries(db, source.user_id, [SeriesType.steps], query, SourceSelection.RECONCILE)
    return [(s.timestamp.date(), float(s.value), s.source.provider if s.source else None) for s in result.data]


class TestReconcileReads:
    def test_a_day_two_devices_hold_is_their_merged_value(self, db: Session, devices: tuple) -> None:
        watch, phone = devices
        _walk(watch, phone, DAY)

        assert _read(db, watch, DAY, DAY) == [(DAY, 180, None)]

    def test_a_day_one_device_holds_is_that_devices_own(self, db: Session, devices: tuple) -> None:
        _, phone = devices
        _steps(phone, DAY, 12, 40)

        assert _read(db, phone, DAY, DAY) == [(DAY, 40, "apple")]

    def test_a_stored_merged_day_is_read_not_merged_again(
        self, db: Session, devices: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        watch, phone = devices
        _walk(watch, phone, DAY)
        SeriesReconcileRepository().reconcile(db, watch.user_id, [DAY], priority_service.get_source_ranking(db))

        def no_merging(*_args: object) -> None:
            raise AssertionError("merged on the fly")

        monkeypatch.setattr(SeriesReconcileRepository, "merge", no_merging)

        assert _read(db, watch, DAY, DAY) == [(DAY, 180, None)]

    def test_a_page_needing_more_merged_days_than_allowed_is_refused(
        self, db: Session, devices: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        watch, phone = devices
        for day in (DAY, DAY + timedelta(days=1)):
            _walk(watch, phone, day)
        monkeypatch.setattr(settings, "reconcile_on_the_fly_max_days", 1)

        with pytest.raises(HTTPException) as refused:
            _read(db, watch, DAY, DAY + timedelta(days=1))

        assert refused.value.status_code == 400
        assert refused.value.detail | {"message": None} == {
            "code": "reconcile_too_many_days",
            "message": None,
            "days": 2,
            "max_days": 1,
            "queued": False,
        }

    def test_with_reconcile_on_the_days_merged_on_the_fly_are_queued_to_be_stored(
        self, db: Session, devices: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        watch, phone = devices
        _walk(watch, phone, DAY)
        for source in devices:
            SeriesRollupRepository().roll_up(db, source.id, [DAY])
        db.merge(ArchivalSetting(id=1, rollup_enabled=True, delete_after_days=None))
        DataMigrationRepository().mark_completed(db, "aggregate_backfill:rollup_all")
        db.flush()
        monkeypatch.setattr(settings, "reconcile_enabled", True)

        assert _read(db, watch, DAY, DAY) == [(DAY, 180, None)]
        assert pop_reconcile_days(10) == [(watch.user_id, DAY)]

    def test_with_reconcile_off_nothing_is_queued(self, db: Session, devices: tuple) -> None:
        watch, phone = devices
        _walk(watch, phone, DAY)

        _read(db, watch, DAY, DAY)

        assert pop_reconcile_days(10) == []


class TestWhichSeriesAreMerged:
    def test_only_summed_series_are_merged(self) -> None:
        """A rate (heart rate) cannot be split by time; the allowlist must never name one."""
        assert all(AGGREGATION_METHOD_BY_TYPE[t] is AggregationMethod.SUM for t in RECONCILED_SERIES)

    def test_a_logged_series_reads_as_per_period(self, db: Session, devices: tuple) -> None:
        """Two apps logging a meal minutes apart are not one meal: no merging, the best-ranked source's day."""
        watch, phone = devices
        energy = db.get(SeriesTypeDefinition, get_series_type_id(SeriesType.dietary_energy_consumed))
        for source, hour, value in ((watch, 12, 600), (phone, 12, 650)):
            DataPointSeriesFactory(
                mapping=source,
                series_type=energy,
                recorded_at=datetime.combine(DAY, datetime.min.time(), timezone.utc) + timedelta(hours=hour),
                window_seconds=60,
                value=value,
            )
        query = TimeSeriesQueryParams(
            start_datetime=datetime.combine(DAY, datetime.min.time(), timezone.utc),
            end_datetime=datetime.combine(DAY + timedelta(days=1), datetime.min.time(), timezone.utc),
            resolution=Resolution.ONE_DAY,
        )

        result = timeseries_service.get_timeseries(
            db, watch.user_id, [SeriesType.dietary_energy_consumed], query, SourceSelection.RECONCILE
        )

        assert [(float(s.value), s.source.provider) for s in result.data] == [(600, "garmin")]


class TestTheReconciledSourceIsNoDevice:
    def test_other_reads_leave_its_rows_out(self, db: Session, devices: tuple) -> None:
        watch, phone = devices
        _walk(watch, phone, DAY)
        for source in devices:
            SeriesRollupRepository().roll_up(db, source.id, [DAY])
        SeriesReconcileRepository().reconcile(db, watch.user_id, [DAY], priority_service.get_source_ranking(db))
        params = TimeSeriesQueryParams(
            start_datetime=datetime(2024, 3, 2, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 3, 3, tzinfo=timezone.utc),
            resolution=Resolution.ONE_DAY,
        )

        every = timeseries_service.get_timeseries(db, watch.user_id, [SeriesType.steps], params)

        assert sorted(float(s.value) for s in every.data) == [120, 150]
        assert {s.id for s in DataSourceRepository(DataSource).get_user_data_sources(db, watch.user_id)} == {
            watch.id,
            phone.id,
        }


class TestReconcileInTheRollup:
    @pytest.fixture(autouse=True)
    def _rollup_and_reconcile_on(self, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        db.merge(ArchivalSetting(id=1, rollup_enabled=True, delete_after_days=None))
        db.flush()
        monkeypatch.setattr(settings, "reconcile_enabled", True)

    def _stored(self, db: Session, user_id: object, day: date) -> list[float]:
        reconciled = SeriesReconcileRepository.reconciled_source(db, user_id)
        if reconciled is None:
            return []
        rows = SeriesReconcileRepository.day_rows(db, reconciled.id, [STEPS], day, day)
        return [float(row.sum) for row in rows.values()]

    def test_recent_days_are_merged_and_stored_old_ones_are_not(self, db: Session, devices: tuple) -> None:
        watch, phone = devices
        recent, old = date.today() - timedelta(days=1), date.today() - timedelta(days=100)
        for day in (recent, old):
            _walk(watch, phone, day)
            requeue_dirty_days([(watch.id, day), (phone.id, day)])

        archival_service.roll_up_queued_days(db)

        assert (self._stored(db, watch.user_id, recent), self._stored(db, watch.user_id, old)) == ([180], [])

    def test_days_its_budget_leaves_stay_queued(
        self, db: Session, devices: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        watch, phone = devices
        _walk(watch, phone, DAY)
        queue_reconcile_days([(watch.user_id, DAY)])
        monkeypatch.setattr(settings, "reconcile_seconds_per_run", 0)

        archival_service.roll_up_queued_days(db)

        assert (self._stored(db, watch.user_id, DAY), pop_reconcile_days(10)) == ([], [(watch.user_id, DAY)])

    def test_the_backfill_rolls_up_without_merging(self, db: Session, devices: tuple) -> None:
        watch, phone = devices
        _walk(watch, phone, DAY)
        queue_reconcile_days([(watch.user_id, DAY)])

        archival_service.roll_up_queued_days(db, reconcile=False)

        assert pop_reconcile_days(10) == [(watch.user_id, DAY)]

    def test_a_read_queued_old_day_is_stored(self, db: Session, devices: tuple) -> None:
        watch, phone = devices
        _walk(watch, phone, DAY)
        queue_reconcile_days([(watch.user_id, DAY)])

        archival_service.roll_up_queued_days(db)

        assert self._stored(db, watch.user_id, DAY) == [180]


class TestReconcileRoute:
    @pytest.mark.parametrize(
        ("params", "detail"),
        [
            ({"resolution": "raw"}, "use resolution 1day"),
            ({"resolution": "1hour"}, "use resolution 1day"),
            ({"resolution": "1day", "provider": "garmin"}, "takes no source filter"),
        ],
    )
    def test_it_needs_day_reads_over_every_source(
        self, client: TestClient, api_v1_prefix: str, params: dict, detail: str
    ) -> None:
        api_key = ApiKeyFactory()
        response = client.get(
            f"{api_v1_prefix}/users/{UserFactory().id}/timeseries",
            headers={"X-Open-Wearables-API-Key": api_key.plain_key},
            params={
                "start_time": "2024-03-01T00:00:00Z",
                "end_time": "2024-03-03T00:00:00Z",
                "types": "steps",
                "source_selection": "reconcile",
                **params,
            },
        )

        assert response.status_code == 400
        assert detail in response.text


def test_reconcile_is_off_by_default() -> None:
    assert (settings.reconcile_enabled, settings.reconcile_stored_days, settings.reconcile_on_the_fly_max_days) == (
        False,
        30,
        30,
    )
