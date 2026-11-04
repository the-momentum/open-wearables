"""source_selection=reconcile: a summed series merged across a user's sources per day, stored by the rollup within
its own budget for recent days, merged on the fly by reads up to a limit."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.config import settings
from app.constants.celery_tasks import CeleryTask
from app.integrations import rollup_queue
from app.integrations.rollup_queue import pop_reconcile_days, queue_reconcile_days, requeue_dirty_days
from app.models import DataSource, ProviderPriority, SeriesSample, SeriesTypeDefinition, User
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
from app.utils.exceptions import ReconcileWindowTooLargeError
from tests.factories import (
    ApiKeyFactory,
    DataPointSeriesFactory,
    DataSourceFactory,
    SeriesTypeDefinitionFactory,
    UserFactory,
    provider_day,
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


def _read(
    db: Session, source: DataSource, first: date, last: date, resolution: Resolution = Resolution.ONE_DAY
) -> list[tuple]:
    query = TimeSeriesQueryParams(
        start_datetime=datetime.combine(first, datetime.min.time(), timezone.utc),
        end_datetime=datetime.combine(last + timedelta(days=1), datetime.min.time(), timezone.utc),
        resolution=resolution,
    )
    result = timeseries_service.get_timeseries(db, source.user_id, [SeriesType.steps], query, SourceSelection.RECONCILE)
    return [(s.timestamp.date(), float(s.value), s.source.provider if s.source else None) for s in result.data]


class TestReconcileReads:
    def test_a_day_two_devices_hold_is_their_merged_value(self, db: Session, devices: tuple) -> None:
        watch, phone = devices
        _walk(watch, phone, DAY)

        assert _read(db, watch, DAY, DAY) == [(DAY, 180, None)]

    def test_a_stored_merge_stays_while_only_another_series_source_is_queued(
        self, db: Session, devices: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        watch, phone = devices
        _walk(watch, phone, DAY)
        for source in devices:
            SeriesRollupRepository().roll_up(db, source.id, [DAY])
        SeriesReconcileRepository().reconcile(db, watch.user_id, [DAY], priority_service.get_source_ranking(db))
        scale = DataSourceFactory(user=db.get(User, watch.user_id), provider=ProviderName.WITHINGS, source="withings")
        requeue_dirty_days([(scale.id, DAY)])
        db.merge(ArchivalSetting(id=1, rollup_enabled=True, delete_after_days=None))
        DataMigrationRepository().mark_completed(db, "aggregate_backfill:rollup_all")
        db.flush()
        monkeypatch.setattr(rollup_queue, "QUEUED_DAYS_TIMEOUT_SECONDS", 5)

        def no_merging(*_args: object) -> None:
            raise AssertionError("merged on the fly")

        monkeypatch.setattr(SeriesReconcileRepository, "merge", no_merging)

        assert _read(db, watch, DAY, DAY) == [(DAY, 180, None)]

    def test_a_day_whose_best_source_holds_only_a_day_value_is_that_value(self, db: Session, devices: tuple) -> None:
        """Oura sends steps only as its day total; ranked first, it is not outvoted by a merge of worse devices."""
        watch, phone = devices
        _walk(watch, phone, DAY)
        ring = DataSourceFactory(user=db.get(User, watch.user_id), provider=ProviderName.OURA, source="oura")
        provider_day(db, ring, SeriesType.steps, DAY, sum=Decimal(9800))
        ProviderPriorityRepository(ProviderPriority).upsert(db, ProviderName.OURA, 0)

        assert _read(db, watch, DAY, DAY) == [(DAY, 9800, "oura")]
        assert (
            SeriesReconcileRepository().merge(db, watch.user_id, [DAY], priority_service.get_source_ranking(db)) == []
        )

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

    def test_a_page_is_shortened_to_the_days_it_may_merge(
        self, db: Session, devices: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        watch, phone = devices
        for day in (DAY, DAY + timedelta(days=1)):
            _walk(watch, phone, day)
        monkeypatch.setattr(settings, "reconcile_on_the_fly_max_days", 1)

        assert _read(db, watch, DAY, DAY + timedelta(days=1)) == [(DAY, 180, None)]

    def test_a_month_with_the_default_budget_is_merged(self, db: Session, devices: tuple) -> None:
        watch, phone = devices
        for offset in range(31):
            _walk(watch, phone, date(2024, 3, 1) + timedelta(days=offset))

        assert _read(db, watch, date(2024, 3, 1), date(2024, 3, 31), Resolution.ONE_MONTH) == [
            (date(2024, 3, 1), 180 * 31, None)
        ]

    def test_a_period_needing_more_merged_days_than_allowed_is_refused(
        self, db: Session, devices: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        watch, phone = devices
        for day in (DAY, DAY + timedelta(days=1)):
            _walk(watch, phone, day)
        monkeypatch.setattr(settings, "reconcile_on_the_fly_max_days", 1)

        with pytest.raises(ReconcileWindowTooLargeError) as refused:
            _read(db, watch, DAY, DAY + timedelta(days=1), Resolution.ONE_WEEK)

        assert refused.value.extensions == {"days": 2, "max_days": 1, "queued": False}

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

    def _rolled_up_with_reconcile_on(self, db: Session, devices: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
        for source in devices:
            SeriesRollupRepository().roll_up(db, source.id, [DAY, DAY + timedelta(days=1)])
        db.merge(ArchivalSetting(id=1, rollup_enabled=True, delete_after_days=None))
        DataMigrationRepository().mark_completed(db, "aggregate_backfill:rollup_all")
        db.flush()
        monkeypatch.setattr(settings, "reconcile_enabled", True)

        def unreachable(*_args: object) -> None:
            raise ConnectionError("redis is down")

        monkeypatch.setattr(rollup_queue, "queue_reconcile_days", unreachable)

    def test_a_queue_that_cannot_be_reached_still_returns_the_merged_day(
        self, db: Session, devices: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        watch, phone = devices
        _walk(watch, phone, DAY)
        self._rolled_up_with_reconcile_on(db, devices, monkeypatch)

        assert _read(db, watch, DAY, DAY) == [(DAY, 180, None)]

    def test_a_refused_page_does_not_claim_days_it_could_not_queue(
        self, db: Session, devices: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        watch, phone = devices
        for day in (DAY, DAY + timedelta(days=1)):
            _walk(watch, phone, day)
        self._rolled_up_with_reconcile_on(db, devices, monkeypatch)
        monkeypatch.setattr(settings, "reconcile_on_the_fly_max_days", 1)

        with pytest.raises(ReconcileWindowTooLargeError) as refused:
            _read(db, watch, DAY, DAY + timedelta(days=1), Resolution.ONE_WEEK)

        assert refused.value.extensions["queued"] is False

    def test_a_stored_merged_day_whose_samples_changed_since_is_merged_again(self, db: Session, devices: tuple) -> None:
        watch, phone = devices
        _walk(watch, phone, DAY)
        for source in devices:
            SeriesRollupRepository().roll_up(db, source.id, [DAY])
        SeriesReconcileRepository().reconcile(db, watch.user_id, [DAY], priority_service.get_source_ranking(db))
        db.merge(ArchivalSetting(id=1, rollup_enabled=True, delete_after_days=None))
        DataMigrationRepository().mark_completed(db, "aggregate_backfill:rollup_all")
        db.flush()
        _steps(phone, DAY, 15, 20)  # walked on with the watch off; the rollup has not caught up yet
        requeue_dirty_days([(phone.id, DAY)])

        assert _read(db, watch, DAY, DAY) == [(DAY, 200, None)]

    def test_with_reconcile_off_nothing_is_queued(self, db: Session, devices: tuple) -> None:
        watch, phone = devices
        _walk(watch, phone, DAY)

        _read(db, watch, DAY, DAY)

        assert pop_reconcile_days(10) == []


class TestEdgeTolerance:
    """A better-ranked sample covers RECONCILE_EDGE_TOLERANCE_SECONDS past its edges, and coverage is the union of
    the better samples' windows, so overlapping better samples never count a second twice."""

    def _merged(self, db: Session, user_id: object) -> list[tuple[float, int]]:
        merged = SeriesReconcileRepository().merge(db, user_id, [DAY], priority_service.get_source_ranking(db))
        return [(round(m.sum), m.count) for m in merged if m.type_id == STEPS]

    def _at(self, source: DataSource, hour: int, minute: int, second: int, seconds: int, value: int) -> None:
        DataPointSeriesFactory(
            mapping=source,
            series_type=SeriesTypeDefinitionFactory.get_or_create_steps(),
            recorded_at=datetime.combine(DAY, datetime.min.time(), timezone.utc)
            + timedelta(hours=hour, minutes=minute, seconds=second),
            window_seconds=seconds,
            value=value,
        )

    def test_one_sensor_read_by_two_apps_a_few_seconds_apart_counts_once(self, db: Session, devices: tuple) -> None:
        """The pattern seen on a real account: a phone's minutes start at :19, the Fitbit app's on the minute."""
        watch, phone = devices
        for minute in range(10):
            self._at(watch, 9, minute, 19, 60, 100)
            self._at(phone, 9, minute, 0, 60, 100)

        assert self._merged(db, watch.user_id)[0][0] == 1000

    def test_without_tolerance_the_offset_leaks_duplicates(
        self, db: Session, devices: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        watch, phone = devices
        monkeypatch.setattr(settings, "reconcile_edge_tolerance_seconds", 0)
        for minute in range(10):
            self._at(watch, 9, minute, 19, 60, 100)
            self._at(phone, 9, minute, 0, 60, 100)

        # The phone's first minute keeps its 19 uncovered seconds: 100 * 19 / 60.
        assert self._merged(db, watch.user_id)[0][0] == 1032

    def test_steps_well_away_from_a_better_device_stay(self, db: Session, devices: tuple) -> None:
        """Watch 09:00-09:02 covers the phone's 09:00-09:05 up to 09:03 with the 60 s tolerance: 2 of 5 minutes stay."""
        watch, phone = devices
        self._at(watch, 9, 0, 0, 60, 100)
        self._at(watch, 9, 1, 0, 60, 100)
        self._at(phone, 9, 0, 0, 300, 300)

        assert self._merged(db, watch.user_id) == [(320, 3)]

    def test_overlapping_better_devices_count_their_seconds_once(
        self, db: Session, devices: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ring's 15:00-15:05 under a watch's 15:00-15:02 and a phone's 15:00-15:03: 15:03-15:05 is the ring's."""
        watch, phone = devices
        ring = DataSourceFactory(
            user=db.get(User, watch.user_id), provider=ProviderName.OURA, source="oura", device_type="ring"
        )
        ProviderPriorityRepository(ProviderPriority).upsert(db, ProviderName.OURA, 3)
        monkeypatch.setattr(settings, "reconcile_edge_tolerance_seconds", 0)
        self._at(watch, 15, 0, 0, 120, 200)
        self._at(phone, 15, 0, 0, 180, 300)
        self._at(ring, 15, 0, 0, 300, 500)

        # watch 200 + phone 300 * 1/3 + ring 500 * 2/5
        assert self._merged(db, watch.user_id)[0][0] == 500


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

    def test_retention_never_overwrites_a_full_merge_with_a_partial_one(self, db: Session, devices: tuple) -> None:
        """Retention deletes a source's samples at a time: what the rest merge without it must not replace the row."""
        watch, phone = devices
        ring = DataSourceFactory(user=db.get(User, watch.user_id), provider=ProviderName.OURA, source="oura")
        ProviderPriorityRepository(ProviderPriority).upsert(db, ProviderName.OURA, 3)
        _walk(watch, phone, DAY)
        _steps(ring, DAY, 12, 30)
        ranking = priority_service.get_source_ranking(db)
        SeriesReconcileRepository().reconcile(db, watch.user_id, [DAY], ranking, keep_existing=True)
        db.query(SeriesSample).filter(SeriesSample.data_source_id == watch.id).delete()

        SeriesReconcileRepository().reconcile(db, watch.user_id, [DAY], ranking, keep_existing=True)

        assert self._stored(db, watch.user_id, DAY) == [180]

    def test_a_priority_change_drops_stored_merges(
        self, db: Session, devices: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        watch, phone = devices
        _walk(watch, phone, DAY)
        SeriesReconcileRepository().reconcile(db, watch.user_id, [DAY], priority_service.get_source_ranking(db))
        sent: list[str] = []
        monkeypatch.setattr("app.services.priority_service.celery_app.send_task", lambda name, **_: sent.append(name))

        priority_service.update_provider_priority(db, ProviderName.APPLE, 1)
        dropped, done = archival_service.drop_reconciled_days(db)

        assert sent == [CeleryTask.DROP_RECONCILED_DAYS]
        assert (dropped, done) == (1, True)
        assert self._stored(db, watch.user_id, DAY) == []

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

    def test_a_failed_merge_is_tried_once_per_run_and_queued_for_the_next(
        self, db: Session, devices: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        watch, phone = devices
        _walk(watch, phone, DAY)
        queue_reconcile_days([(watch.user_id, DAY)])
        calls = []

        def failing(*args: object, **kwargs: object) -> int:
            calls.append(args)
            raise RuntimeError("merge failed")

        monkeypatch.setattr(archival_service.reconcile_repo, "reconcile", failing)

        archival_service.roll_up_queued_days(db)

        assert (len(calls), pop_reconcile_days(10)) == (1, [(watch.user_id, DAY)])

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

    def test_a_period_over_the_budget_answers_with_the_numbers(
        self, client: TestClient, api_v1_prefix: str, db: Session, devices: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        watch, phone = devices
        for day in (DAY, DAY + timedelta(days=1)):
            _walk(watch, phone, day)
        monkeypatch.setattr(settings, "reconcile_on_the_fly_max_days", 1)

        response = client.get(
            f"{api_v1_prefix}/users/{watch.user_id}/timeseries",
            headers={"X-Open-Wearables-API-Key": ApiKeyFactory().plain_key},
            params={
                "start_time": "2024-03-02T00:00:00Z",
                "end_time": "2024-03-04T00:00:00Z",
                "types": "steps",
                "resolution": "1week",
                "source_selection": "reconcile",
            },
        )

        assert response.status_code == 400
        body = response.json()
        assert (body["code"], body["days"], body["max_days"], body["queued"]) == (
            "RECONCILE_TOO_MANY_DAYS",
            2,
            1,
            False,
        )


def test_reconcile_is_off_by_default() -> None:
    assert (settings.reconcile_enabled, settings.reconcile_stored_days, settings.reconcile_on_the_fly_max_days) == (
        False,
        30,
        31,
    )
