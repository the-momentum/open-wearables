"""Tests for flagging the naps of providers that don't report them (#938)."""

import importlib
from datetime import date, datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.integrations.redis_client import get_redis_client
from app.models import DataSource, EventRecord, SleepDetails
from app.schemas.enums import ProviderName
from app.schemas.providers.mobile_sdk import SyncRequest
from app.services.sdk.sleep_service import handle_sleep_data, key
from app.services.sleep_naps import NapChange, SleepWindow, find_naps, reclassify_naps
from app.services.summaries_service import SummariesService
from tests.factories import DataSourceFactory, EventRecordFactory, SleepDetailsFactory, UserFactory

# The package re-exports the service instance under the module's name, so the module comes from importlib
nap_service = importlib.import_module("app.services.event_record_service")


def _session(start: str, end: str, asleep_minutes: int, zone: str | None = "+02:00") -> SleepWindow:
    """A session given in local time at `zone` (UTC when None)."""
    suffix = zone or "+00:00"
    return SleepWindow(
        id=uuid4(),
        start=datetime.fromisoformat(start + suffix),
        end=datetime.fromisoformat(end + suffix),
        zone_offset=zone,
        asleep=timedelta(minutes=asleep_minutes),
    )


NIGHT = ("2026-03-22T23:00", "2026-03-23T07:00", 450)


class TestFindNaps:
    def test_an_afternoon_nap_far_from_the_night_is_a_nap(self) -> None:
        night = _session(*NIGHT)
        nap = _session("2026-03-23T13:00", "2026-03-23T14:30", 80)

        assert find_naps([night, nap]) == {nap.id}

    def test_sleep_touching_the_main_sleep_is_not_a_nap(self) -> None:
        # A day sleep after a night shift, and more sleep right after it
        day_sleep = _session("2026-03-23T08:00", "2026-03-23T15:00", 400)
        after = _session("2026-03-23T15:00", "2026-03-23T16:00", 60)

        assert find_naps([day_sleep, after]) == set()

    def test_an_evening_sleep_close_to_the_next_night_is_not_a_nap(self) -> None:
        night = _session(*NIGHT)
        evening = _session("2026-03-23T18:00", "2026-03-23T19:30", 80)
        next_night = _session("2026-03-23T21:00", "2026-03-24T07:00", 540)

        assert find_naps([night, evening, next_night]) == set()

    def test_a_day_with_only_a_nap_keeps_it_as_main_sleep(self) -> None:
        assert find_naps([_session("2026-03-23T13:00", "2026-03-23T14:30", 80)]) == set()

    def test_a_nap_is_more_than_two_hours_from_the_night(self) -> None:
        night = _session(*NIGHT)
        at_the_limit = _session("2026-03-23T09:00", "2026-03-23T10:30", 80)
        past_it = _session("2026-03-23T09:01", "2026-03-23T10:30", 80)

        assert find_naps([night, at_the_limit]) == set()
        assert find_naps([night, past_it]) == {past_it.id}

    def test_on_a_tie_the_earlier_session_is_the_main_sleep(self) -> None:
        morning = _session("2026-03-23T08:00", "2026-03-23T10:00", 120)
        afternoon = _session("2026-03-23T14:00", "2026-03-23T16:00", 120)

        assert find_naps([afternoon, morning]) == {afternoon.id}

    def test_three_hours_of_sleep_is_not_a_nap(self) -> None:
        night = _session(*NIGHT)
        three_hours = _session("2026-03-23T12:00", "2026-03-23T15:30", 180)
        just_under = _session("2026-03-24T12:00", "2026-03-24T15:30", 179)
        next_night = _session("2026-03-23T23:00", "2026-03-24T07:00", 450)

        assert find_naps([night, three_hours, next_night, just_under]) == {just_under.id}

    def test_less_than_fifteen_minutes_of_sleep_is_not_a_nap(self) -> None:
        night = _session(*NIGHT)
        short = _session("2026-03-23T13:00", "2026-03-23T13:20", 14)
        long_enough = _session("2026-03-23T16:00", "2026-03-23T16:20", 15)

        assert find_naps([night, short, long_enough]) == {long_enough.id}

    def test_a_nap_starts_from_06_00_to_before_20_00_local_time(self) -> None:
        # The night ends at 03:00, and no night follows, so only the start hour decides
        night = _session("2026-03-22T21:00", "2026-03-23T03:00", 330)
        before_six = _session("2026-03-23T05:59", "2026-03-23T06:59", 60)
        at_six = _session("2026-03-23T06:00", "2026-03-23T07:00", 60)
        before_eight_pm = _session("2026-03-23T19:59", "2026-03-23T20:59", 60)
        at_eight_pm = _session("2026-03-23T20:00", "2026-03-23T21:00", 60)

        assert find_naps([night, before_six]) == set()
        assert find_naps([night, at_six]) == {at_six.id}
        assert find_naps([night, before_eight_pm]) == {before_eight_pm.id}
        assert find_naps([night, at_eight_pm]) == set()

    def test_the_first_part_of_a_night_split_after_20_00_is_not_a_nap(self) -> None:
        # A real night: 20:13-23:54, then the rest from 02:08, a gap of 2 h 14
        night = _session(*NIGHT)
        first_part = _session("2026-03-23T20:13", "2026-03-23T23:54", 161)
        rest = _session("2026-03-24T02:08", "2026-03-24T07:00", 290)

        assert find_naps([night, first_part, rest]) == set()

    def test_a_session_is_read_in_its_own_zone_offset(self) -> None:
        # 19:00-20:00 at -05:00 is 00:00-01:00 UTC the next day: still a nap of the 23rd, starting at 19:00
        night = _session(*NIGHT, zone="-05:00")
        nap = _session("2026-03-23T19:00", "2026-03-23T20:00", 60, zone="-05:00")

        assert find_naps([night, nap]) == {nap.id}

    def test_without_a_zone_offset_sleep_close_to_the_night_is_not_a_nap(self) -> None:
        # The second half of a night at +12:00, 04:30-06:30, reads as 16:30-18:30 in UTC, 3 h after the first
        night = _session("2026-03-23T09:00", "2026-03-23T13:30", 250, zone=None)
        second_half = _session("2026-03-23T16:30", "2026-03-23T18:30", 110, zone=None)

        assert find_naps([night, second_half]) == set()

    def test_without_a_zone_offset_a_nap_is_more_than_four_hours_from_the_night(self) -> None:
        night = _session(*NIGHT, zone=None)
        at_four_hours = _session("2026-03-23T11:00", "2026-03-23T12:00", 60, zone=None)
        after_four_hours = _session("2026-03-23T11:01", "2026-03-23T12:00", 59, zone=None)

        assert find_naps([night, at_four_hours]) == set()
        assert find_naps([night, after_four_hours]) == {after_four_hours.id}

    def test_without_a_zone_offset_the_start_hour_is_not_checked(self) -> None:
        # A 13:00 nap at +11:00 reads as 02:00 in UTC, between nights read as 12:00-20:00
        night = _session("2026-03-22T12:00", "2026-03-22T20:00", 450, zone=None)
        nap = _session("2026-03-23T02:00", "2026-03-23T03:00", 60, zone=None)
        next_night = _session("2026-03-23T12:00", "2026-03-23T20:00", 450, zone=None)

        assert find_naps([night, nap, next_night]) == {nap.id}

    def test_without_a_zone_offset_the_issue_nap_is_a_nap(self) -> None:
        # #938's example: a 16 min nap that Garmin Connect wrote to Apple Health without a zone offset
        night = _session("2026-04-17T22:22", "2026-04-18T04:35", 372, zone=None)
        nap = _session("2026-04-18T13:48", "2026-04-18T14:04", 16, zone=None)

        assert find_naps([night, nap]) == {nap.id}

    def test_a_nap_more_than_two_hours_before_the_next_night_is_a_nap(self) -> None:
        night = _session(*NIGHT)
        nap = _session("2026-03-23T18:40", "2026-03-23T20:02", 80)
        next_night = _session("2026-03-23T23:32", "2026-03-24T07:00", 420)

        assert find_naps([night, nap, next_night]) == {nap.id}

    def test_the_main_sleep_has_the_most_sleep_not_the_longest_window(self) -> None:
        most_sleep = _session("2026-03-23T08:00", "2026-03-23T10:00", 115)
        longer_window = _session("2026-03-23T13:00", "2026-03-23T16:30", 90)

        assert find_naps([longer_window, most_sleep]) == {longer_window.id}


def _record(source: DataSource, start: str, end: str, zone: str = "+00:00") -> EventRecord:
    """A stored sleep record given in local time at `zone`."""
    start_dt, end_dt = datetime.fromisoformat(start + zone), datetime.fromisoformat(end + zone)
    return EventRecordFactory(
        data_source=source,
        category="sleep",
        type="sleep_session",
        start_datetime=start_dt,
        end_datetime=end_dt,
        duration_seconds=int((end_dt - start_dt).total_seconds()),
        zone_offset=zone,
    )


def _stored(
    source: DataSource, start: str, end: str, asleep_minutes: int, is_nap: bool | None = False, zone: str = "+00:00"
) -> SleepDetails:
    """A stored session given in local time at `zone`."""
    record = _record(source, start, end, zone)
    return SleepDetailsFactory(event_record=record, sleep_total_duration_minutes=asleep_minutes, is_nap=is_nap)


def _source() -> DataSource:
    # A provider without nap flags that stores a zone offset
    return DataSourceFactory(provider=ProviderName.WITHINGS, source="withings")


def _is_nap(db: Session, details: SleepDetails) -> bool | None:
    db.expire_all()
    return db.get(SleepDetails, details.record_id).is_nap


class TestReclassifyNaps:
    def test_flags_a_nap_and_returns_the_change(self, db: Session) -> None:
        source = _source()
        night = _stored(source, "2026-03-22T23:00", "2026-03-23T07:00", 450)
        nap = _stored(source, "2026-03-23T13:00", "2026-03-23T14:30", 80)

        changes = reclassify_naps(db, source.id, {date(2026, 3, 23)})

        assert changes == [NapChange(nap.record_id, True, date(2026, 3, 23))]
        assert _is_nap(db, nap) is True
        assert _is_nap(db, night) is False

    def test_unflags_a_nap_that_is_main_sleep_now(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.APPLE, source="apple")
        alone = _stored(source, "2026-03-23T13:00", "2026-03-23T14:30", 80, is_nap=True)

        assert reclassify_naps(db, source.id, {date(2026, 3, 23)}) == [
            NapChange(alone.record_id, False, date(2026, 3, 23))
        ]
        assert _is_nap(db, alone) is False

    def test_leaves_a_provider_that_flags_naps_alone(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.GARMIN, source="garmin")
        _stored(source, "2026-03-22T23:00", "2026-03-23T07:00", 450)
        nap = _stored(source, "2026-03-23T13:00", "2026-03-23T14:30", 80)

        assert reclassify_naps(db, source.id, {date(2026, 3, 23)}) == []
        assert _is_nap(db, nap) is False

    def test_only_reflags_the_days_around_the_given_ones(self, db: Session) -> None:
        source = _source()
        _stored(source, "2026-03-22T23:00", "2026-03-23T07:00", 450)
        near = _stored(source, "2026-03-23T13:00", "2026-03-23T14:30", 80)
        _stored(source, "2026-03-26T23:00", "2026-03-27T07:00", 450)
        far = _stored(source, "2026-03-27T13:00", "2026-03-27T14:30", 80)

        reclassify_naps(db, source.id, {date(2026, 3, 24)})

        assert _is_nap(db, near) is True
        assert _is_nap(db, far) is False

    def test_none_reflags_the_whole_history(self, db: Session) -> None:
        source = _source()
        _stored(source, "2025-01-09T23:00", "2025-01-10T07:00", 450)
        old_nap = _stored(source, "2025-01-10T13:00", "2025-01-10T14:30", 80)

        reclassify_naps(db, source.id, None)

        assert _is_nap(db, old_nap) is True

    def test_a_dry_run_leaves_the_session_clean(self, db: Session) -> None:
        source = _source()
        _stored(source, "2026-03-22T23:00", "2026-03-23T07:00", 450)
        nap = _stored(source, "2026-03-23T13:00", "2026-03-23T14:30", 80)

        assert len(reclassify_naps(db, source.id, None, dry_run=True)) == 1
        assert nap.is_nap is False

    def test_reflags_the_day_after_against_its_next_night(self, db: Session) -> None:
        source = _source()
        _stored(source, "2026-03-23T23:00", "2026-03-24T07:00", 450)
        nap = _stored(source, "2026-03-24T13:00", "2026-03-24T14:30", 80)
        evening = _stored(source, "2026-03-24T18:00", "2026-03-24T19:30", 80)
        _stored(source, "2026-03-24T21:00", "2026-03-25T07:00", 540)

        assert reclassify_naps(db, source.id, {date(2026, 3, 23)}) == [
            NapChange(nap.record_id, True, date(2026, 3, 24))
        ]
        assert _is_nap(db, evening) is False

    def test_leaves_the_lookahead_day_alone(self, db: Session) -> None:
        source = _source()
        flagged = _stored(source, "2026-03-25T13:00", "2026-03-25T14:30", 80, is_nap=True)

        assert reclassify_naps(db, source.id, {date(2026, 3, 23)}) == []
        assert _is_nap(db, flagged) is True

    def test_loads_the_day_before_east_of_utc(self, db: Session) -> None:
        # The night of the 22nd at +09:00 ends on the 21st in UTC
        source = _source()
        _stored(source, "2026-03-21T23:00", "2026-03-22T07:00", 450, zone="+09:00")
        nap = _stored(source, "2026-03-22T13:00", "2026-03-22T14:30", 80, zone="+09:00")

        reclassify_naps(db, source.id, {date(2026, 3, 23)})

        assert _is_nap(db, nap) is True

    def test_a_missing_flag_counts_as_not_a_nap(self, db: Session) -> None:
        source = _source()
        night = _stored(source, "2026-03-22T23:00", "2026-03-23T07:00", 450, is_nap=None)
        nap = _stored(source, "2026-03-23T13:00", "2026-03-23T14:30", 80)

        assert reclassify_naps(db, source.id, {date(2026, 3, 23)}) == [
            NapChange(nap.record_id, True, date(2026, 3, 23))
        ]
        assert _is_nap(db, night) is None

    def test_a_record_without_details_counts_by_its_length(self, db: Session) -> None:
        source = _source()
        _record(source, "2026-03-22T23:00", "2026-03-23T07:00")
        nap = _stored(source, "2026-03-23T13:00", "2026-03-23T14:30", 80)

        reclassify_naps(db, source.id, {date(2026, 3, 23)})

        assert _is_nap(db, nap) is True

    def test_time_asleep_wins_over_the_session_length(self, db: Session) -> None:
        source = _source()
        _stored(source, "2026-03-23T08:00", "2026-03-23T10:00", 115)
        longer_window = _stored(source, "2026-03-23T13:00", "2026-03-23T16:30", 90)

        reclassify_naps(db, source.id, {date(2026, 3, 23)})

        assert _is_nap(db, longer_window) is True

    def test_no_dates_change_nothing(self, db: Session) -> None:
        source = _source()
        _stored(source, "2026-03-22T23:00", "2026-03-23T07:00", 450)
        _stored(source, "2026-03-23T13:00", "2026-03-23T14:30", 80)

        assert reclassify_naps(db, source.id, set()) == []

    def test_counts_sessions_the_caller_has_not_flushed(self, db: Session) -> None:
        source = _source()
        nap = _stored(source, "2026-03-23T13:00", "2026-03-23T14:30", 80)
        night_id = uuid4()
        db.add(
            EventRecord(
                id=night_id,
                data_source_id=source.id,
                category="sleep",
                type="sleep_session",
                source_name="x",
                duration_seconds=28800,
                zone_offset="+00:00",
                start_datetime=datetime.fromisoformat("2026-03-22T23:00+00:00"),
                end_datetime=datetime.fromisoformat("2026-03-23T07:00+00:00"),
            )
        )
        db.add(SleepDetails(record_id=night_id, sleep_total_duration_minutes=450, is_nap=False))

        assert reclassify_naps(db, source.id, {date(2026, 3, 23)}) == [
            NapChange(nap.record_id, True, date(2026, 3, 23))
        ]


NIGHT_UPLOAD = (("light", "2026-03-22T23:00:00Z", "2026-03-23T07:00:00Z"),)
NAP_UPLOAD = (("sleeping", "2026-03-23T13:00:00Z", "2026-03-23T14:30:00Z"),)


def _sdk_sleep(*samples: tuple[str, str, str]) -> SyncRequest:
    source = {"name": "Apple Watch", "device_type": "watch", "device_model": "Watch7,1"}
    return SyncRequest.model_validate(
        {
            "provider": "apple",
            "sdkVersion": "1.0.0",
            "syncTimestamp": "2026-03-23T20:00:00Z",
            "data": {
                "records": [],
                "workouts": [],
                "sleep": [
                    {
                        "id": str(uuid4()),
                        "stage": stage,
                        "startDate": start,
                        "endDate": end,
                        "zoneOffset": "+00:00",
                        "source": source,
                    }
                    for stage, start, end in samples
                ],
            },
        }
    )


def _flags(db: Session, user_id: UUID) -> dict[str, bool | None]:
    db.expire_all()
    rows = (
        db.query(EventRecord)
        .join(DataSource, EventRecord.data_source_id == DataSource.id)
        .filter(DataSource.user_id == user_id, EventRecord.category == "sleep")
        .all()
    )
    return {record.start_datetime.strftime("%H:%M"): record.sleep_detail.is_nap for record in rows}


class TestSdkNaps:
    @pytest.mark.parametrize(
        "uploads", [(NIGHT_UPLOAD, NAP_UPLOAD), (NAP_UPLOAD, NIGHT_UPLOAD)], ids=["night_first", "nap_first"]
    )
    @patch("app.services.sdk.sleep_service.celery_app")
    def test_the_nap_is_flagged_in_either_upload_order(
        self, mock_celery: MagicMock, db: Session, uploads: tuple[tuple[tuple[str, str, str], ...], ...]
    ) -> None:
        user = UserFactory()
        for upload in uploads:
            handle_sleep_data(db, _sdk_sleep(*upload), str(user.id))

        db.rollback()  # the flag must be committed, not just flushed
        assert _flags(db, user.id) == {"23:00": False, "13:00": True}

    @patch("app.services.sdk.sleep_service.celery_app")
    def test_the_summary_counts_the_nap_apart(self, mock_celery: MagicMock, db: Session) -> None:
        user = UserFactory()
        handle_sleep_data(db, _sdk_sleep(*NIGHT_UPLOAD), str(user.id))
        handle_sleep_data(db, _sdk_sleep(*NAP_UPLOAD), str(user.id))

        page = SummariesService().get_sleep_summaries(
            db,
            user.id,
            datetime(2026, 3, 22, tzinfo=timezone.utc),
            datetime(2026, 3, 25, tzinfo=timezone.utc),
            None,
            10,
        )

        (day,) = [summary for summary in page.data if summary.date == date(2026, 3, 23)]
        assert day.duration_minutes == 480
        assert day.nap_count == 1

    @patch("app.services.sdk.sleep_service.celery_app")
    def test_a_failed_reflag_on_the_first_session_leaves_the_next_one_flagged(
        self, mock_celery: MagicMock, db: Session
    ) -> None:
        user = UserFactory()
        real = nap_service.reclassify_naps
        calls: list[int] = []

        def fail_once(session: Session, *args: Any, **kwargs: Any) -> list[NapChange]:
            calls.append(1)
            if len(calls) == 1:
                session.execute(text("SELECT 1/0"))
            return real(session, *args, **kwargs)

        with patch.object(nap_service, "reclassify_naps", side_effect=fail_once):
            handle_sleep_data(db, _sdk_sleep(*NIGHT_UPLOAD, *NAP_UPLOAD), str(user.id))

        assert len(calls) == 2
        assert _flags(db, user.id) == {"23:00": False, "13:00": True}
        assert not get_redis_client().exists(key(str(user.id)))

    @patch("app.services.sdk.sleep_service.celery_app")
    def test_a_failed_reflag_keeps_the_session_and_clears_the_state(self, mock_celery: MagicMock, db: Session) -> None:
        user = UserFactory()
        handle_sleep_data(db, _sdk_sleep(*NIGHT_UPLOAD), str(user.id))

        def fail(session: Session, *args: Any, **kwargs: Any) -> None:
            session.execute(text("SELECT 1/0"))

        with patch.object(nap_service, "reclassify_naps", side_effect=fail):
            handle_sleep_data(db, _sdk_sleep(*NAP_UPLOAD), str(user.id))

        assert _flags(db, user.id) == {"23:00": False, "13:00": False}
        assert not get_redis_client().exists(key(str(user.id)))
