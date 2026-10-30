"""Tests for SummariesService."""

import math
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from logging import getLogger
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import DataSource, EventRecordAggregate, ProviderPriority
from app.models.archival_setting import ArchivalSetting
from app.repositories import AggregateRepository, ProviderPriorityRepository
from app.repositories.data_migration_repository import DataMigrationRepository
from app.schemas.enums import ComputedBy, HealthScoreCategory, ProviderName, SeriesType
from app.services.summaries_service import SummariesService
from tests.factories import (
    DataPointSeriesFactory,
    DataSourceFactory,
    EventRecordFactory,
    HealthScoreFactory,
    PersonalRecordFactory,
    SeriesTypeDefinitionFactory,
    SleepDetailsFactory,
    UserFactory,
    WorkoutDetailsFactory,
    provider_day,
    roll_up_everything,
)


@pytest.fixture
def service() -> SummariesService:
    return SummariesService(log=getLogger(__name__))


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _rollup_reached_the_history(db: Session) -> None:
    db.merge(ArchivalSetting(id=1, rollup_enabled=True, delete_after_days=None))
    DataMigrationRepository().mark_completed(db, "aggregate_backfill:rollup_all")
    db.flush()


# ---------------------------------------------------------------------------
# _filter_by_priority
# ---------------------------------------------------------------------------


class TestFilterByPriority:
    def test_returns_empty_for_empty_input(self, db: Session, service: SummariesService) -> None:
        result = service._filter_by_priority(db, uuid4(), [])
        assert result == []

    def test_single_entry_passes_through(self, db: Session, service: SummariesService) -> None:
        entry = {"activity_date": date(2026, 1, 1), "source": "garmin", "device_model": None}
        result = service._filter_by_priority(db, uuid4(), [entry])
        assert result == [entry]

    def test_picks_one_entry_per_date(self, db: Session, service: SummariesService) -> None:
        entries = [
            {"activity_date": date(2026, 1, 1), "source": "garmin", "device_model": None},
            {"activity_date": date(2026, 1, 1), "source": "apple_health_sdk", "device_model": None},
            {"activity_date": date(2026, 1, 2), "source": "garmin", "device_model": None},
        ]
        result = service._filter_by_priority(db, uuid4(), entries)
        assert len(result) == 2
        dates = {r["activity_date"] for r in result}
        assert dates == {date(2026, 1, 1), date(2026, 1, 2)}

    def test_uses_sleep_date_key(self, db: Session, service: SummariesService) -> None:
        entries = [
            {"sleep_date": date(2026, 1, 1), "source": "garmin", "device_model": None},
            {"sleep_date": date(2026, 1, 1), "source": "oura", "device_model": None},
        ]
        result = service._filter_by_priority(db, uuid4(), entries, date_key="sleep_date")
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _get_user_max_hr
# ---------------------------------------------------------------------------


class TestGetUserMaxHr:
    def test_falls_back_to_default_when_no_user(self, db: Session, service: SummariesService) -> None:
        result = service._get_user_max_hr(db, uuid4(), datetime(2026, 1, 1, tzinfo=timezone.utc))
        assert result == 190

    def test_falls_back_to_default_when_no_birth_date(self, db: Session, service: SummariesService) -> None:
        user = UserFactory()
        PersonalRecordFactory(user=user, birth_date=None)
        result = service._get_user_max_hr(db, user.id, datetime(2026, 1, 1, tzinfo=timezone.utc))
        assert result == 190

    def test_calculates_from_birth_date(self, db: Session, service: SummariesService) -> None:
        user = UserFactory()
        PersonalRecordFactory(user=user, birth_date=date(1990, 6, 1))
        ref = datetime(2026, 6, 26, tzinfo=timezone.utc)  # age = 36
        result = service._get_user_max_hr(db, user.id, ref)
        assert result == 220 - 36

    def test_adjusts_when_birthday_not_yet_this_year(self, db: Session, service: SummariesService) -> None:
        user = UserFactory()
        PersonalRecordFactory(user=user, birth_date=date(1990, 12, 31))
        ref = datetime(2026, 6, 26, tzinfo=timezone.utc)  # birthday hasn't happened yet -> age 35
        result = service._get_user_max_hr(db, user.id, ref)
        assert result == 220 - 35


# ---------------------------------------------------------------------------
# get_sleep_summaries
# ---------------------------------------------------------------------------


class TestGetSleepSummaries:
    def _make_sleep_record(self, user: Any, start: str, end: str) -> Any:
        ds = DataSourceFactory(user=user, provider=ProviderName.GARMIN, source="garmin")
        return EventRecordFactory(
            data_source=ds,
            category="sleep",
            type="sleep",
            start_datetime=_dt(start),
            end_datetime=_dt(end),
            duration_seconds=int((_dt(end) - _dt(start)).total_seconds()),
            zone_offset="+00:00",
        )

    def test_activity_totals_cut_by_the_bounds_utc_dates_like_the_rest_of_the_summary(
        self, db: Session, service: SummariesService
    ) -> None:
        """end=today at noon excludes today, as the workout and sleep queries of the same summary do."""
        source = DataSourceFactory(provider=ProviderName.GARMIN, source="garmin")
        provider_day(db, source, SeriesType.steps, date(2026, 3, 1), sum=Decimal("1000"))
        provider_day(db, source, SeriesType.steps, date(2026, 3, 2), sum=Decimal("2000"))

        totals = service.get_activity_totals(
            db, source.user_id, _dt("2026-03-01T00:00:00+00:00"), _dt("2026-03-02T12:00:00+00:00")
        )

        assert (totals.days, totals.steps) == (1, 1000)

    def test_a_bad_cursor_is_the_clients_error(self, db: Session, service: SummariesService) -> None:
        with pytest.raises(HTTPException) as raised:
            service.get_sleep_summaries(
                db, uuid4(), _dt("2026-01-01T00:00:00+00:00"), _dt("2026-01-07T00:00:00+00:00"), cursor="?", limit=10
            )
        assert raised.value.status_code == 400

    def test_returns_empty_when_no_data(self, db: Session, service: SummariesService) -> None:
        user = UserFactory()
        result = service.get_sleep_summaries(
            db,
            user.id,
            _dt("2026-01-01T00:00:00+00:00"),
            _dt("2026-01-07T00:00:00+00:00"),
            cursor=None,
            limit=10,
        )
        assert result.data == []
        assert result.pagination.has_more is False

    def test_returns_sleep_record(self, db: Session, service: SummariesService) -> None:
        user = UserFactory()
        record = self._make_sleep_record(user, "2026-01-01T23:00:00+00:00", "2026-01-02T07:00:00+00:00")
        SleepDetailsFactory(event_record=record)

        result = service.get_sleep_summaries(
            db,
            user.id,
            _dt("2026-01-01T00:00:00+00:00"),
            _dt("2026-01-03T00:00:00+00:00"),
            cursor=None,
            limit=10,
        )
        assert len(result.data) == 1
        summary = result.data[0]
        assert summary.duration_minutes == 8 * 60
        assert summary.source.provider == "garmin"

    def test_a_day_value_sent_inside_the_sleep_counts_as_before(self, db: Session, service: SummariesService) -> None:
        """Oura sends the night's SpO2 as a day value at 00:00 UTC, inside the sleep."""
        user = UserFactory()
        record = self._make_sleep_record(user, "2026-01-01T23:00:00+00:00", "2026-01-02T07:00:00+00:00")
        SleepDetailsFactory(event_record=record)
        source = db.get(DataSource, record.data_source_id)
        provider_day(db, source, SeriesType.oxygen_saturation, date(2026, 1, 2), avg=Decimal("96.5"))

        result = service.get_sleep_summaries(
            db, user.id, _dt("2026-01-01T00:00:00+00:00"), _dt("2026-01-03T00:00:00+00:00"), cursor=None, limit=10
        )

        assert [night.avg_spo2_percent for night in result.data] == [96.5]

    def test_does_not_return_other_users_data(self, db: Session, service: SummariesService) -> None:
        user_a = UserFactory()
        user_b = UserFactory()
        self._make_sleep_record(user_b, "2026-01-01T23:00:00+00:00", "2026-01-02T07:00:00+00:00")

        result = service.get_sleep_summaries(
            db,
            user_a.id,
            _dt("2026-01-01T00:00:00+00:00"),
            _dt("2026-01-03T00:00:00+00:00"),
            cursor=None,
            limit=10,
        )
        assert result.data == []

    def test_physio_averages_within_sleep_window(self, db: Session, service: SummariesService) -> None:
        """avg_heart_rate_bpm/avg_hrv_sdnn_ms are computed from series_sample
        samples within [min_start_time, max_end_time), independently per series
        type, and samples outside the window are excluded."""
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.GARMIN, source="garmin")
        record = EventRecordFactory(
            data_source=ds,
            category="sleep",
            type="sleep",
            start_datetime=_dt("2026-01-01T23:00:00+00:00"),
            end_datetime=_dt("2026-01-02T07:00:00+00:00"),
            duration_seconds=8 * 3600,
            zone_offset="+00:00",
        )
        SleepDetailsFactory(event_record=record)

        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        hrv_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate_variability_sdnn()

        for i, val in enumerate([50, 60, 70]):
            DataPointSeriesFactory(
                data_source=ds,
                series_type=hr_type,
                value=val,
                recorded_at=_dt(f"2026-01-02T0{i}:00:00+00:00"),
            )
        DataPointSeriesFactory(
            data_source=ds,
            series_type=hrv_type,
            value=45,
            recorded_at=_dt("2026-01-02T02:00:00+00:00"),
        )
        # Outside the sleep window - must not affect the average
        DataPointSeriesFactory(
            data_source=ds,
            series_type=hr_type,
            value=200,
            recorded_at=_dt("2026-01-02T12:00:00+00:00"),
        )

        roll_up_everything(db)

        result = service.get_sleep_summaries(
            db,
            user.id,
            _dt("2026-01-01T00:00:00+00:00"),
            _dt("2026-01-03T00:00:00+00:00"),
            cursor=None,
            limit=10,
        )
        assert len(result.data) == 1
        summary = result.data[0]
        assert summary.avg_heart_rate_bpm == 60
        assert summary.avg_hrv_sdnn_ms == 45

    def test_a_night_takes_its_own_sleeps_values_the_providers_first(
        self, db: Session, service: SummariesService
    ) -> None:
        """The ring's own night value wins over ours; the watch worn the same night fills only what the ring lacks."""
        user = UserFactory()
        ring = DataSourceFactory(user=user, provider=ProviderName.OURA, source="oura")
        watch = DataSourceFactory(user=user, provider=ProviderName.APPLE, source="apple")
        record = EventRecordFactory(
            data_source=ring,
            category="sleep",
            type="sleep",
            start_datetime=_dt("2026-01-01T23:00:00+00:00"),
            end_datetime=_dt("2026-01-02T07:00:00+00:00"),
            duration_seconds=8 * 3600,
            zone_offset="+00:00",
        )
        SleepDetailsFactory(event_record=record)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        hrv_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate_variability_sdnn()
        for hour, value in enumerate([60, 62]):
            DataPointSeriesFactory(
                data_source=ring, series_type=hr_type, value=value, recorded_at=_dt(f"2026-01-02T0{hour}:00:00+00:00")
            )
        DataPointSeriesFactory(
            data_source=watch, series_type=hrv_type, value=45, recorded_at=_dt("2026-01-02T02:00:00+00:00")
        )
        roll_up_everything(db)
        AggregateRepository(EventRecordAggregate).upsert(
            db,
            [
                {
                    "record_id": record.id,
                    "series_type_definition_id": hr_type.id,
                    "computed_by": ComputedBy.PROVIDER,
                    "avg": Decimal("52"),
                    "count": 1,
                }
            ],
        )

        summary = service.get_sleep_summaries(
            db, user.id, _dt("2026-01-01T00:00:00+00:00"), _dt("2026-01-03T00:00:00+00:00"), cursor=None, limit=10
        ).data[0]

        assert (summary.avg_heart_rate_bpm, summary.avg_hrv_sdnn_ms) == (52, 45.0)

    def test_a_night_not_rolled_up_yet_reads_its_own_devices_samples_first(
        self, db: Session, service: SummariesService
    ) -> None:
        """Before the 15-minute rollup has reached the night, the sleep's own watch is read, not the phone."""
        user = UserFactory()
        watch = DataSourceFactory(user=user, provider=ProviderName.APPLE, source="Apple Watch")
        phone = DataSourceFactory(user=user, provider=ProviderName.APPLE, source="iPhone")
        record = EventRecordFactory(
            data_source=watch,
            category="sleep",
            type="sleep",
            start_datetime=_dt("2026-01-01T23:00:00+00:00"),
            end_datetime=_dt("2026-01-02T07:00:00+00:00"),
            duration_seconds=8 * 3600,
            zone_offset="+00:00",
        )
        SleepDetailsFactory(event_record=record)
        hrv_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate_variability_sdnn()
        for source, value in ((watch, 50), (phone, 30)):
            DataPointSeriesFactory(
                data_source=source, series_type=hrv_type, value=value, recorded_at=_dt("2026-01-02T02:00:00+00:00")
            )

        summary = service.get_sleep_summaries(
            db, user.id, _dt("2026-01-01T00:00:00+00:00"), _dt("2026-01-03T00:00:00+00:00"), cursor=None, limit=10
        ).data[0]

        assert summary.avg_hrv_sdnn_ms == 50

    def test_physio_averages_none_without_physio_data(self, db: Session, service: SummariesService) -> None:
        user = UserFactory()
        record = self._make_sleep_record(user, "2026-01-01T23:00:00+00:00", "2026-01-02T07:00:00+00:00")
        SleepDetailsFactory(event_record=record)

        result = service.get_sleep_summaries(
            db,
            user.id,
            _dt("2026-01-01T00:00:00+00:00"),
            _dt("2026-01-03T00:00:00+00:00"),
            cursor=None,
            limit=10,
        )
        assert len(result.data) == 1
        summary = result.data[0]
        assert summary.avg_heart_rate_bpm is None
        assert summary.avg_hrv_sdnn_ms is None
        assert summary.avg_hrv_rmssd_ms is None
        assert summary.avg_respiratory_rate is None
        assert summary.avg_spo2_percent is None

    def test_has_more_flag_and_pagination(self, db: Session, service: SummariesService) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.GARMIN, source="garmin")
        for day in range(1, 6):
            EventRecordFactory(
                data_source=ds,
                category="sleep",
                type="sleep",
                start_datetime=_dt(f"2026-01-{day:02d}T23:00:00+00:00"),
                end_datetime=_dt(f"2026-01-{day + 1:02d}T07:00:00+00:00"),
                duration_seconds=8 * 3600,
                zone_offset="+00:00",
            )

        result = service.get_sleep_summaries(
            db,
            user.id,
            _dt("2026-01-01T00:00:00+00:00"),
            _dt("2026-01-10T00:00:00+00:00"),
            cursor=None,
            limit=3,
        )
        assert len(result.data) == 3
        assert result.pagination.has_more is True
        assert result.pagination.next_cursor is not None


class TestSleepPagingPerDate:
    """A page holds `limit` nights, however many sources recorded each one."""

    NIGHTS = [date(2026, 1, day) for day in range(2, 7)]
    START = _dt("2026-01-01T00:00:00+00:00")
    END = _dt("2026-01-31T00:00:00+00:00")

    def _two_sources_per_night(self, db: Session) -> Any:
        """Garmin and Oura both record every night; Garmin wins each one.

        The losing Oura record gets the lower id, so within a night it sorts first:
        a page cut between the two rows would elect Oura.
        """
        priorities = ProviderPriorityRepository(ProviderPriority)
        priorities.upsert(db, ProviderName.GARMIN, 1)
        priorities.upsert(db, ProviderName.OURA, 2)
        user = UserFactory()
        garmin = DataSourceFactory(user=user, provider=ProviderName.GARMIN, source="garmin", device_type="watch")
        oura = DataSourceFactory(user=user, provider=ProviderName.OURA, source="oura", device_type="ring")
        for n, night in enumerate(self.NIGHTS):
            wake = datetime(night.year, night.month, night.day, 7, tzinfo=timezone.utc)
            for ds, id_prefix in ((oura, "00000000"), (garmin, "ffffffff")):
                EventRecordFactory(
                    id=UUID(f"{id_prefix}-0000-0000-0000-{n:012d}"),
                    data_source=ds,
                    category="sleep",
                    type="sleep",
                    start_datetime=wake - timedelta(hours=8),
                    end_datetime=wake,
                    duration_seconds=8 * 3600,
                    zone_offset="+00:00",
                )
        return user

    @pytest.mark.parametrize("limit", [1, 2])
    def test_pages_forward_through_every_night_once(self, db: Session, service: SummariesService, limit: int) -> None:
        user = self._two_sources_per_night(db)

        seen: list[tuple[date, str]] = []
        has_more: list[bool] = []
        cursor = None
        while True:
            page = service.get_sleep_summaries(db, user.id, self.START, self.END, cursor=cursor, limit=limit)
            seen += [(summary.date, summary.source.provider) for summary in page.data]
            has_more.append(page.pagination.has_more)
            if not page.pagination.next_cursor:
                break
            cursor = page.pagination.next_cursor

        assert seen == [(night, "garmin") for night in self.NIGHTS]
        # Only the last page says there is nothing more
        assert has_more == [True] * (math.ceil(len(self.NIGHTS) / limit) - 1) + [False]

    def test_previous_cursor_returns_the_page_before(self, db: Session, service: SummariesService) -> None:
        user = self._two_sources_per_night(db)
        first = service.get_sleep_summaries(db, user.id, self.START, self.END, cursor=None, limit=2)
        second = service.get_sleep_summaries(
            db, user.id, self.START, self.END, cursor=first.pagination.next_cursor, limit=2
        )
        third = service.get_sleep_summaries(
            db, user.id, self.START, self.END, cursor=second.pagination.next_cursor, limit=2
        )

        back = service.get_sleep_summaries(
            db, user.id, self.START, self.END, cursor=third.pagination.previous_cursor, limit=2
        )

        assert sorted((s.date, s.source.provider) for s in back.data) == [
            (night, "garmin") for night in self.NIGHTS[2:4]
        ]
        assert back.pagination.has_more is True


# ---------------------------------------------------------------------------
# get_recovery_summaries
# ---------------------------------------------------------------------------


class TestGetRecoverySummaries:
    def test_rmssd_input_is_exposed_as_rmssd_not_sdnn(
        self, service: SummariesService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        row = {
            "recovery_date": date(2026, 1, 2),
            "provider": "whoop",
            "source": "whoop",
            "device_model": "WHOOP",
            "device_type": "band",
            "record_id": uuid4(),
            "recorded_at": _dt("2026-01-02T00:00:00+00:00"),
            "recovery_score": 74,
            "resting_heart_rate": 51,
            "hrv_rmssd_milli": 63.2,
            "spo2_percentage": 98.4,
        }
        monkeypatch.setattr(service.health_score_repo, "get_recovery_summaries", lambda *_: [row])
        monkeypatch.setattr(service, "_priority_orders", lambda *_: ({}, {}))

        result = service.get_recovery_summaries(
            db_session=None,
            user_id=uuid4(),
            start_date=_dt("2026-01-01T00:00:00+00:00"),
            end_date=_dt("2026-01-03T00:00:00+00:00"),
            cursor=None,
            limit=10,
        )

        summary = result.data[0]
        assert summary.avg_hrv_sdnn_ms is None
        assert summary.avg_hrv_rmssd_ms == 63.2


class TestRecoveryPagingPerDate:
    """A page holds `limit` days, however many providers scored each one."""

    DAYS = [date(2026, 1, day) for day in range(2, 7)]
    START = _dt("2026-01-01T00:00:00+00:00")
    END = _dt("2026-01-31T00:00:00+00:00")

    def _two_providers_per_day(self, db: Session) -> Any:
        """WHOOP and Polar both score every day; WHOOP wins each one.

        The losing Polar score gets the lower id at the same timestamp, so within a day
        it sorts first: a page cut between the two rows would elect Polar.
        """
        priorities = ProviderPriorityRepository(ProviderPriority)
        priorities.upsert(db, ProviderName.WHOOP, 1)
        priorities.upsert(db, ProviderName.POLAR, 2)
        user = UserFactory()
        whoop = DataSourceFactory(user=user, provider=ProviderName.WHOOP, source="whoop", device_type="band")
        polar = DataSourceFactory(user=user, provider=ProviderName.POLAR, source="polar", device_type="watch")
        for n, day in enumerate(self.DAYS):
            scored_at = datetime(day.year, day.month, day.day, 7, tzinfo=timezone.utc)
            for ds, provider, id_prefix in (
                (polar, ProviderName.POLAR, "00000000"),
                (whoop, ProviderName.WHOOP, "ffffffff"),
            ):
                HealthScoreFactory(
                    id=UUID(f"{id_prefix}-0000-0000-0000-{n:012d}"),
                    data_source=ds,
                    provider=provider,
                    category=HealthScoreCategory.RECOVERY,
                    recorded_at=scored_at,
                )
        return user

    @pytest.mark.parametrize("limit", [1, 2])
    def test_pages_forward_through_every_day_once(self, db: Session, service: SummariesService, limit: int) -> None:
        user = self._two_providers_per_day(db)

        seen: list[tuple[date, str]] = []
        has_more: list[bool] = []
        cursor = None
        while True:
            page = service.get_recovery_summaries(db, user.id, self.START, self.END, cursor=cursor, limit=limit)
            seen += [(summary.date, summary.source.provider) for summary in page.data]
            has_more.append(page.pagination.has_more)
            if not page.pagination.next_cursor:
                break
            cursor = page.pagination.next_cursor

        assert seen == [(day, "whoop") for day in self.DAYS]
        # Only the last page says there is nothing more
        assert has_more == [True] * (math.ceil(len(self.DAYS) / limit) - 1) + [False]

    def test_previous_cursor_returns_the_page_before(self, db: Session, service: SummariesService) -> None:
        user = self._two_providers_per_day(db)
        first = service.get_recovery_summaries(db, user.id, self.START, self.END, cursor=None, limit=2)
        second = service.get_recovery_summaries(
            db, user.id, self.START, self.END, cursor=first.pagination.next_cursor, limit=2
        )
        third = service.get_recovery_summaries(
            db, user.id, self.START, self.END, cursor=second.pagination.next_cursor, limit=2
        )

        back = service.get_recovery_summaries(
            db, user.id, self.START, self.END, cursor=third.pagination.previous_cursor, limit=2
        )

        assert sorted((s.date, s.source.provider) for s in back.data) == [
            (self.DAYS[2], "whoop"),
            (self.DAYS[3], "whoop"),
        ]


# ---------------------------------------------------------------------------
# get_activity_summaries
# ---------------------------------------------------------------------------


class TestGetActivitySummaries:
    def test_returns_empty_when_no_data(self, db: Session, service: SummariesService) -> None:
        user = UserFactory()
        result = service.get_activity_summaries(
            db,
            user.id,
            _dt("2026-01-01T00:00:00+00:00"),
            _dt("2026-01-07T00:00:00+00:00"),
            cursor=None,
            limit=10,
        )
        assert result.data == []

    def test_aggregates_steps_for_user(self, db: Session, service: SummariesService) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.APPLE, source="apple_health_sdk")
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()

        for i in range(3):
            DataPointSeriesFactory(
                data_source=ds,
                series_type=steps_type,
                value=1000,
                recorded_at=_dt(f"2026-01-01T10:0{i}:00+00:00"),
            )

        roll_up_everything(db)

        result = service.get_activity_summaries(
            db,
            user.id,
            _dt("2026-01-01T00:00:00+00:00"),
            _dt("2026-01-02T00:00:00+00:00"),
            cursor=None,
            limit=10,
        )
        assert len(result.data) == 1
        assert result.data[0].steps == 3000

    def _apple_steps(self, user: Any, values: list[int]) -> Any:
        ds = DataSourceFactory(user=user, provider=ProviderName.APPLE, source="apple_health_sdk")
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()
        for i, value in enumerate(values):
            DataPointSeriesFactory(
                data_source=ds, series_type=steps_type, value=value, recorded_at=_dt(f"2026-01-01T10:0{i}:00+00:00")
            )
        return ds

    def _day(self, db: Session, service: SummariesService, user: Any) -> list:
        return service.get_activity_summaries(
            db, user.id, _dt("2026-01-01T00:00:00+00:00"), _dt("2026-01-02T00:00:00+00:00"), cursor=None, limit=10
        ).data

    def test_a_day_without_a_day_row_is_counted_from_the_samples(self, db: Session, service: SummariesService) -> None:
        user = UserFactory()
        self._apple_steps(user, [1000, 250])

        assert [day.steps for day in self._day(db, service, user)] == [1250]

    def test_a_day_row_wins_over_the_samples(self, db: Session, service: SummariesService) -> None:
        user = UserFactory()
        ds = self._apple_steps(user, [1000, 250])
        provider_day(db, ds, SeriesType.steps, date(2026, 1, 1), sum=Decimal("9000"))

        assert [day.steps for day in self._day(db, service, user)] == [9000]

    def test_once_the_rollup_reached_the_history_the_samples_are_not_read(
        self, db: Session, service: SummariesService
    ) -> None:
        user = UserFactory()
        self._apple_steps(user, [1000, 250])
        _rollup_reached_the_history(db)

        assert self._day(db, service, user) == []

    def test_includes_days_with_only_a_workout(self, db: Session, service: SummariesService) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.STRAVA, source="strava")
        EventRecordFactory(
            data_source=ds,
            category="workout",
            type="running",
            start_datetime=_dt("2026-01-01T10:00:00+00:00"),
            end_datetime=_dt("2026-01-01T11:00:00+00:00"),
            zone_offset="+00:00",
        )

        result = service.get_activity_summaries(
            db,
            user.id,
            _dt("2026-01-01T00:00:00+00:00"),
            _dt("2026-01-02T00:00:00+00:00"),
            cursor=None,
            limit=10,
        )
        assert [(d.date, d.source.provider, d.steps) for d in result.data] == [(date(2026, 1, 1), "strava", None)]

    def test_takes_elevation_from_the_winning_provider_only(self, db: Session, service: SummariesService) -> None:
        # Without a ranking both tie, and the winner would be whichever row the database returned first.
        priorities = ProviderPriorityRepository(ProviderPriority)
        priorities.upsert(db, ProviderName.GARMIN, 1)
        priorities.upsert(db, ProviderName.STRAVA, 2)
        user = UserFactory()
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()
        elevations = {ProviderName.GARMIN: "100", ProviderName.STRAVA: "900"}
        for provider, elevation in elevations.items():
            ds = DataSourceFactory(user=user, provider=provider, source="watch", device_model="Forerunner 965")
            WorkoutDetailsFactory(
                event_record=EventRecordFactory(
                    data_source=ds,
                    category="workout",
                    start_datetime=_dt("2026-01-01T10:00:00+00:00"),
                    end_datetime=_dt("2026-01-01T11:00:00+00:00"),
                    zone_offset="+00:00",
                ),
                total_elevation_gain=Decimal(elevation),
            )
            if provider == ProviderName.GARMIN:
                DataPointSeriesFactory(
                    data_source=ds, series_type=steps_type, value=1000, recorded_at=_dt("2026-01-01T10:00:00+00:00")
                )

        result = service.get_activity_summaries(
            db,
            user.id,
            _dt("2026-01-01T00:00:00+00:00"),
            _dt("2026-01-02T00:00:00+00:00"),
            cursor=None,
            limit=10,
        )
        assert [(d.source.provider, d.elevation_meters) for d in result.data] == [("garmin", 100.0)]

    def test_does_not_return_other_users_data(self, db: Session, service: SummariesService) -> None:
        user_a = UserFactory()
        user_b = UserFactory()
        ds = DataSourceFactory(user=user_b)
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()
        DataPointSeriesFactory(
            data_source=ds, series_type=steps_type, value=5000, recorded_at=_dt("2026-01-01T10:00:00+00:00")
        )

        result = service.get_activity_summaries(
            db,
            user_a.id,
            _dt("2026-01-01T00:00:00+00:00"),
            _dt("2026-01-02T00:00:00+00:00"),
            cursor=None,
            limit=10,
        )
        assert result.data == []


class TestActivityPagingWindow:
    """Each page aggregates only a window of days around it, widened as needed."""

    def test_pages_through_sparse_days_without_skipping_or_repeating(
        self, db: Session, service: SummariesService
    ) -> None:
        # A day a month for two years: far sparser than any first window, so every
        # page has to widen it, and the cursor must still hand over cleanly.
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.APPLE, source="apple_health_sdk")
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()
        start = _dt("2024-01-01T00:00:00+00:00")
        days = [start + timedelta(days=30 * i, hours=10) for i in range(25)]
        for at in days:
            DataPointSeriesFactory(data_source=ds, series_type=steps_type, value=1000, recorded_at=at)
        expected = [at.date() for at in days]
        end = _dt("2026-06-01T00:00:00+00:00")

        for order, want in (("desc", list(reversed(expected))), ("asc", expected)):
            seen: list[date] = []
            cursor = None
            pages = []
            while True:
                roll_up_everything(db)
                page = service.get_activity_summaries(db, user.id, start, end, cursor=cursor, limit=3, sort_order=order)
                pages.append(page)
                seen += [summary.date for summary in page.data]
                if not page.pagination.next_cursor:
                    break
                cursor = page.pagination.next_cursor
            assert seen == want

            # Back from the third page lands on the second.
            back = service.get_activity_summaries(
                db, user.id, start, end, cursor=pages[2].pagination.previous_cursor, limit=3, sort_order=order
            )
            assert sorted(summary.date for summary in back.data) == sorted(summary.date for summary in pages[1].data)


class TestActivityTotals:
    def test_adds_up_the_days_the_summaries_return(self, db: Session, service: SummariesService) -> None:
        # The total is defined by the daily summaries, so it is checked against them.
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.APPLE, source="apple_health_sdk")
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()
        start = _dt("2026-01-01T00:00:00+00:00")
        for day, value in ((0, 1000), (1, 3000), (5, 2000)):
            DataPointSeriesFactory(
                data_source=ds, series_type=steps_type, value=value, recorded_at=start + timedelta(days=day, hours=10)
            )
        end = _dt("2026-02-01T00:00:00+00:00")

        roll_up_everything(db)

        totals = service.get_activity_totals(db, user.id, start, end)
        days = service.get_activity_summaries(db, user.id, start, end, cursor=None, limit=100).data

        assert totals.days == len(days) == 3
        assert totals.steps == sum(day.steps or 0 for day in days) == 6000
        assert totals.avg_steps == 2000

    def test_a_day_without_steps_has_none_and_stays_out_of_the_average(
        self, db: Session, service: SummariesService
    ) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.APPLE, source="apple_health_sdk")
        start = _dt("2026-01-01T00:00:00+00:00")
        DataPointSeriesFactory(
            data_source=ds,
            series_type=SeriesTypeDefinitionFactory.get_or_create_steps(),
            value=3000,
            recorded_at=start + timedelta(hours=10),
        )
        DataPointSeriesFactory(
            data_source=ds,
            series_type=SeriesTypeDefinitionFactory.get_or_create_heart_rate(),
            value=60,
            recorded_at=start + timedelta(days=1, hours=10),
        )
        end = _dt("2026-01-03T00:00:00+00:00")

        roll_up_everything(db)

        days = service.get_activity_summaries(db, user.id, start, end, cursor=None, limit=10).data
        totals = service.get_activity_totals(db, user.id, start, end)

        assert [day.steps for day in days] == [3000, None]
        assert (totals.days, totals.avg_steps) == (2, 3000)

    def test_is_empty_without_data(self, db: Session, service: SummariesService) -> None:
        totals = service.get_activity_totals(
            db, UserFactory().id, _dt("2026-01-01T00:00:00+00:00"), _dt("2026-02-01T00:00:00+00:00")
        )
        assert (totals.days, totals.steps, totals.avg_steps) == (0, 0, None)


class TestBodySummaryAverages:
    def test_a_resting_pulse_sent_on_the_sleep_counts_beside_the_day_values(
        self, db: Session, service: SummariesService
    ) -> None:
        """Oura, Whoop, Suunto and Withings send the night's resting pulse on the sleep, not on the day."""
        user = UserFactory()
        watch = DataSourceFactory(user=user, provider=ProviderName.GARMIN, source="garmin")
        ring = DataSourceFactory(user=user, provider=ProviderName.OURA, source="oura")
        yesterday = date.today() - timedelta(days=1)
        provider_day(db, watch, SeriesType.resting_heart_rate, yesterday, avg=Decimal("60"))
        night = EventRecordFactory(
            data_source=ring,
            category="sleep",
            type="sleep",
            start_datetime=datetime.combine(yesterday, datetime.min.time(), timezone.utc) - timedelta(hours=1),
            end_datetime=datetime.combine(yesterday, datetime.min.time(), timezone.utc) + timedelta(hours=7),
            zone_offset="+00:00",
        )
        rhr = SeriesTypeDefinitionFactory.get_or_create_resting_heart_rate()
        AggregateRepository(EventRecordAggregate).upsert(
            db,
            [
                {
                    "record_id": night.id,
                    "series_type_definition_id": rhr.id,
                    "computed_by": ComputedBy.PROVIDER,
                    "avg": Decimal("52"),
                    "count": 1,
                }
            ],
        )

        body = service.get_body_summary(db, user.id, 7, 24)

        assert body is not None
        assert body.averaged.resting_heart_rate_bpm == 56

    def test_a_resting_pulse_without_a_day_row_is_counted_from_the_samples(
        self, db: Session, service: SummariesService
    ) -> None:
        user = UserFactory()
        phone = DataSourceFactory(user=user, provider=ProviderName.APPLE, source="apple_health_sdk")
        rhr = SeriesTypeDefinitionFactory.get_or_create_resting_heart_rate()
        noon = datetime.combine(date.today() - timedelta(days=1), datetime.min.time(), timezone.utc) + timedelta(
            hours=12
        )
        for minutes, value in ((0, 50), (30, 54)):
            DataPointSeriesFactory(
                data_source=phone, series_type=rhr, value=value, recorded_at=noon + timedelta(minutes=minutes)
            )

        body = service.get_body_summary(db, user.id, 7, 24)

        assert body is not None
        assert body.averaged.resting_heart_rate_bpm == 52
