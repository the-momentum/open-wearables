"""
Tests for EventRecordService.

Tests cover:
- Creating event record details
- Getting formatted event records with filters
- Counting workouts by type
- create_or_merge_sleep: adjacent session merging
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models import DataSource
from app.schemas.model_crud.activities import EventRecordCreate, EventRecordDetailCreate, EventRecordQueryParams
from app.schemas.model_crud.activities.sleep import SleepStage
from app.services.event_record_service import event_record_service
from tests.factories import DataSourceFactory, EventRecordFactory, SleepDetailsFactory, UserFactory


class TestEventRecordServiceCreateDetail:
    """Test creating event record details."""

    def test_create_detail_with_heart_rate_metrics(self, db: Session) -> None:
        """Should create event record detail with heart rate metrics."""
        # Arrange
        event_record = EventRecordFactory(category="workout", type_="running")
        detail_payload = EventRecordDetailCreate(
            record_id=event_record.id,
            heart_rate_min=120,
            heart_rate_max=180,
            heart_rate_avg=Decimal("150.5"),
        )

        # Act
        detail = event_record_service.create_detail(db, detail_payload)

        # Assert (using getattr for polymorphic attributes)
        assert detail.record_id is not None
        assert detail.record_id == event_record.id
        assert getattr(detail, "heart_rate_min") == 120
        assert getattr(detail, "heart_rate_max") == 180
        assert getattr(detail, "heart_rate_avg") == Decimal("150.5")

    def test_create_detail_with_step_metrics(self, db: Session) -> None:
        """Should create event record detail with step metrics."""
        # Arrange
        event_record = EventRecordFactory(category="workout")
        detail_payload = EventRecordDetailCreate(
            record_id=event_record.id,
            steps_count=5000,
        )

        # Act
        detail = event_record_service.create_detail(db, detail_payload)

        # Assert (using getattr for polymorphic attributes)
        assert getattr(detail, "steps_count") == 5000

    def test_create_detail_with_workout_metrics(self, db: Session) -> None:
        """Should create event record detail with workout metrics."""
        # Arrange
        event_record = EventRecordFactory(category="workout", type_="cycling")
        detail_payload = EventRecordDetailCreate(
            record_id=event_record.id,
            max_speed=Decimal("35.5"),
            average_speed=Decimal("25.2"),
            max_watts=Decimal("350.0"),
            average_watts=Decimal("210.5"),
            moving_time_seconds=3600,
            total_elevation_gain=Decimal("450.0"),
            elev_high=Decimal("1200.0"),
            elev_low=Decimal("750.0"),
        )

        # Act
        detail = event_record_service.create_detail(db, detail_payload)

        # Assert (using getattr for polymorphic attributes)
        assert getattr(detail, "max_speed") == Decimal("35.5")
        assert getattr(detail, "average_speed") == Decimal("25.2")
        assert getattr(detail, "max_watts") == Decimal("350.0")
        assert getattr(detail, "average_watts") == Decimal("210.5")
        assert getattr(detail, "moving_time_seconds") == 3600
        assert getattr(detail, "total_elevation_gain") == Decimal("450.0")

    def test_create_detail_minimal_data(self, db: Session) -> None:
        """Should create event record detail with minimal data."""
        # Arrange
        event_record = EventRecordFactory()
        detail_payload = EventRecordDetailCreate(record_id=event_record.id)

        # Act
        detail = event_record_service.create_detail(db, detail_payload)

        # Assert (using getattr for polymorphic attributes)
        assert detail.record_id is not None
        assert detail.record_id == event_record.id
        # All optional fields should be None
        assert getattr(detail, "heart_rate_min", None) is None
        assert getattr(detail, "steps_count", None) is None


class TestEventRecordServiceBulkCreateDetails:
    """bulk_create_details must dispatch a webhook per detail on commit.

    Before the fix, Apple/Google/Samsung SDK imports saved workouts through
    bulk_create + bulk_create_details and no webhook was ever emitted.
    """

    def test_bulk_create_details_emits_workout_webhooks(self, db: Session) -> None:
        data_source = DataSourceFactory(source="apple")
        rec1 = EventRecordFactory(mapping=data_source, category="workout", type_="running")
        rec2 = EventRecordFactory(mapping=data_source, category="workout", type_="cycling")

        details = [
            EventRecordDetailCreate(
                record_id=rec1.id,
                energy_burned=Decimal("300.0"),
                distance=Decimal("5000.0"),
            ),
            EventRecordDetailCreate(
                record_id=rec2.id,
                energy_burned=Decimal("500.0"),
                distance=Decimal("20000.0"),
            ),
        ]

        with (
            patch("app.services.event_record_service.svix_service.is_enabled", return_value=True),
            patch("app.services.event_record_service.on_workout_created") as mock_workout,
        ):
            event_record_service.bulk_create_details(db, details, detail_type="workout")
            db.commit()

        assert mock_workout.call_count == 2
        dispatched_ids = {c.kwargs["record_id"] for c in mock_workout.call_args_list}
        assert dispatched_ids == {rec1.id, rec2.id}

    def test_bulk_create_details_silent_when_svix_disabled(self, db: Session) -> None:
        data_source = DataSourceFactory(source="apple")
        rec = EventRecordFactory(mapping=data_source, category="workout", type_="running")

        details = [EventRecordDetailCreate(record_id=rec.id, energy_burned=Decimal("250.0"))]

        with (
            patch("app.services.event_record_service.svix_service.is_enabled", return_value=False),
            patch("app.services.event_record_service.on_workout_created") as mock_workout,
        ):
            event_record_service.bulk_create_details(db, details, detail_type="workout")
            db.commit()

        mock_workout.assert_not_called()

    def test_bulk_create_details_empty_list_is_noop(self, db: Session) -> None:
        with (
            patch("app.services.event_record_service.svix_service.is_enabled", return_value=True),
            patch("app.services.event_record_service.on_workout_created") as mock_workout,
        ):
            event_record_service.bulk_create_details(db, [], detail_type="workout")
            db.commit()

        mock_workout.assert_not_called()


class TestEventRecordServiceGetRecordsResponse:
    """Test getting formatted event records."""

    def test_get_records_response_basic(self, db: Session) -> None:
        """Should return formatted event records."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user, source="apple")
        record = EventRecordFactory(
            mapping=mapping,
            category="workout",
            type_="running",
        )

        query_params = EventRecordQueryParams(category="workout")

        # Act
        records = event_record_service.get_records_response(db, query_params, str(user.id))

        # Assert
        assert len(records) >= 1
        matching_record = next((r for r in records if r.id == record.id), None)
        assert matching_record is not None
        assert matching_record.user_id == user.id
        assert matching_record.source == "apple"
        assert matching_record.category == "workout"
        assert matching_record.type == "running"

    def test_get_records_response_filters_by_category(self, db: Session) -> None:
        """Should filter records by category."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)

        workout_record = EventRecordFactory(mapping=mapping, category="workout")
        sleep_record = EventRecordFactory(mapping=mapping, category="sleep")

        query_params = EventRecordQueryParams(category="workout")

        # Act
        records = event_record_service.get_records_response(db, query_params, str(user.id))

        # Assert
        record_ids = [r.id for r in records]
        assert workout_record.id in record_ids
        assert sleep_record.id not in record_ids

    def test_get_records_response_filters_by_type(self, db: Session) -> None:
        """Should filter records by type."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)

        running_record = EventRecordFactory(mapping=mapping, category="workout", type_="running")
        cycling_record = EventRecordFactory(mapping=mapping, category="workout", type_="cycling")

        query_params = EventRecordQueryParams(category="workout", record_type="running")

        # Act
        records = event_record_service.get_records_response(db, query_params, str(user.id))

        # Assert
        record_ids = [r.id for r in records]
        assert running_record.id in record_ids
        assert cycling_record.id not in record_ids

    def test_get_records_response_filters_by_device_id(self, db: Session) -> None:
        """Should filter records by device_id."""
        # Arrange
        user = UserFactory()
        mapping1 = DataSourceFactory(user=user, device_model="device_1")
        mapping2 = DataSourceFactory(user=user, device_model="device_2")

        record1 = EventRecordFactory(mapping=mapping1)
        record2 = EventRecordFactory(mapping=mapping2)

        query_params = EventRecordQueryParams(category="workout", device_model="device_1")

        # Act
        records = event_record_service.get_records_response(db, query_params, str(user.id))

        # Assert
        record_ids = [r.id for r in records]
        assert record1.id in record_ids
        assert record2.id not in record_ids

    def test_get_records_response_filters_by_provider(self, db: Session) -> None:
        """Should filter records by provider_name."""
        # Arrange
        user = UserFactory()
        apple_mapping = DataSourceFactory(user=user, source="apple")
        garmin_mapping = DataSourceFactory(user=user, source="garmin")

        apple_record = EventRecordFactory(mapping=apple_mapping)
        garmin_record = EventRecordFactory(mapping=garmin_mapping)

        query_params = EventRecordQueryParams(category="workout", source="apple")

        # Act
        records = event_record_service.get_records_response(db, query_params, str(user.id))

        # Assert
        record_ids = [r.id for r in records]
        assert apple_record.id in record_ids
        assert garmin_record.id not in record_ids

    def test_get_records_response_user_isolation(self, db: Session) -> None:
        """Should only return records for specified user."""
        # Arrange
        user1 = UserFactory(email="user1@example.com")
        user2 = UserFactory(email="user2@example.com")

        mapping1 = DataSourceFactory(user=user1)
        mapping2 = DataSourceFactory(user=user2)

        record1 = EventRecordFactory(mapping=mapping1)
        record2 = EventRecordFactory(mapping=mapping2)

        query_params = EventRecordQueryParams(category="workout")

        # Act
        records = event_record_service.get_records_response(db, query_params, str(user1.id))

        # Assert
        record_ids = [r.id for r in records]
        assert record1.id in record_ids
        assert record2.id not in record_ids

    def test_get_records_response_empty_result(self, db: Session) -> None:
        """Should return empty list when no records match."""
        # Arrange
        user = UserFactory()
        query_params = EventRecordQueryParams(category="workout")

        # Act
        records = event_record_service.get_records_response(db, query_params, str(user.id))

        # Assert
        assert records == []


class TestEventRecordServiceGetCountByWorkoutType:
    """Test counting workouts by type."""

    def test_get_count_by_workout_type_groups_correctly(self, db: Session) -> None:
        """Should group and count workouts by type."""
        # Arrange
        mapping = DataSourceFactory()

        # Create multiple workouts of different types
        EventRecordFactory(mapping=mapping, category="workout", type_="running")
        EventRecordFactory(mapping=mapping, category="workout", type_="running")
        EventRecordFactory(mapping=mapping, category="workout", type_="running")
        EventRecordFactory(mapping=mapping, category="workout", type_="cycling")
        EventRecordFactory(mapping=mapping, category="workout", type_="cycling")
        EventRecordFactory(mapping=mapping, category="workout", type_="swimming")

        # Act
        results = event_record_service.get_count_by_workout_type(db)

        # Assert
        results_dict = dict(results)
        assert results_dict.get("running") == 3
        assert results_dict.get("cycling") == 2
        assert results_dict.get("swimming") == 1

    def test_get_count_by_workout_type_ordered_by_count(self, db: Session) -> None:
        """Should order results by count descending."""
        # Arrange
        mapping = DataSourceFactory()

        # Create workouts with different counts
        EventRecordFactory(mapping=mapping, type_="running")
        EventRecordFactory(mapping=mapping, type_="cycling")
        EventRecordFactory(mapping=mapping, type_="cycling")

        # Act
        results = event_record_service.get_count_by_workout_type(db)

        # Assert
        # Results should be ordered by count descending
        assert results[0][1] >= results[1][1]  # First count >= second count

    def test_get_count_by_workout_type_handles_null_type(self, db: Session) -> None:
        """Should handle records with null type."""
        # Arrange
        mapping = DataSourceFactory()

        EventRecordFactory(mapping=mapping, type_=None)
        EventRecordFactory(mapping=mapping, type_=None)
        EventRecordFactory(mapping=mapping, type_="running")

        # Act
        results = event_record_service.get_count_by_workout_type(db)

        # Assert
        results_dict = dict(results)
        assert results_dict.get(None) == 2
        assert results_dict.get("running") == 1

    def test_get_count_by_workout_type_empty_result(self, db: Session) -> None:
        """Should return empty list when no workout records exist."""
        # Act
        results = event_record_service.get_count_by_workout_type(db)

        # Assert
        assert results == []


class TestCreateOrMergeSleep:
    """Test create_or_merge_sleep adjacent session merging."""

    THRESHOLD = 120  # minutes, matching settings.sleep_end_gap_minutes default

    def _dt(self, hour: int, minute: int = 0, day: int = 21) -> datetime:
        return datetime(2026, 3, day, hour, minute, tzinfo=timezone.utc)

    def _record(self, data_source: DataSource, start: datetime, end: datetime) -> EventRecordCreate:
        return EventRecordCreate(
            id=uuid4(),
            category="sleep",
            type="sleep_session",
            source_name=data_source.source or "test",
            source=data_source.source,
            user_id=data_source.user_id,
            data_source_id=data_source.id,
            start_datetime=start,
            end_datetime=end,
            duration_seconds=int((end - start).total_seconds()),
        )

    def _detail(
        self,
        record_id: UUID,
        *,
        deep: int = 60,
        light: int = 120,
        rem: int = 60,
        awake: int = 10,
        in_bed: int = 260,
        efficiency: str = "80.00",
        is_nap: bool = False,
    ) -> EventRecordDetailCreate:
        total = deep + light + rem
        return EventRecordDetailCreate(
            record_id=record_id,
            sleep_deep_minutes=deep,
            sleep_light_minutes=light,
            sleep_rem_minutes=rem,
            sleep_awake_minutes=awake,
            sleep_total_duration_minutes=total,
            sleep_time_in_bed_minutes=in_bed,
            sleep_efficiency_score=Decimal(efficiency),
            is_nap=is_nap,
        )

    def test_no_adjacent_creates_single_record(self, db: Session) -> None:
        """When no adjacent record exists, creates the record normally."""
        data_source = DataSourceFactory()
        start, end = self._dt(1, 35), self._dt(8, 51)
        record = self._record(data_source, start, end)
        detail = self._detail(record.id)

        result = event_record_service.create_or_merge_sleep(db, data_source.user_id, record, detail, self.THRESHOLD)

        assert result.id == record.id
        assert result.start_datetime == start
        assert result.end_datetime == end

    def test_adjacent_within_threshold_is_merged(self, db: Session) -> None:
        """Sessions within threshold_minutes of each other are merged into one record."""
        user = UserFactory()
        data_source = DataSourceFactory(user=user)

        # Existing short session: 20:56–21:26 (30 min)
        existing = EventRecordFactory(
            mapping=data_source,
            category="sleep",
            type_="sleep_session",
            start_datetime=self._dt(20, 56),
            end_datetime=self._dt(21, 26),
            duration_seconds=1800,
        )
        SleepDetailsFactory(
            event_record=existing,
            sleep_deep_minutes=0,
            sleep_light_minutes=8,
            sleep_rem_minutes=0,
            sleep_awake_minutes=22,
            sleep_total_duration_minutes=8,
            sleep_time_in_bed_minutes=30,
        )

        # New main session: 22:25–07:40 (gap of ~59 min from existing end)
        start, end = self._dt(22, 25), self._dt(7, 40, day=22)
        record = self._record(data_source, start, end)
        detail = self._detail(record.id, deep=90, light=200, rem=80, awake=30, in_bed=430)

        result = event_record_service.create_or_merge_sleep(db, user.id, record, detail, self.THRESHOLD)

        assert result.start_datetime == self._dt(20, 56)
        assert result.end_datetime == self._dt(7, 40, day=22)
        # duration_seconds covers the full merged window, not the sum of parts
        assert result.duration_seconds == int((self._dt(7, 40, day=22) - self._dt(20, 56)).total_seconds())

    def test_merge_sums_stage_minutes(self, db: Session) -> None:
        """Merged record stage minutes equal the sum of both sessions."""
        user = UserFactory()
        data_source = DataSourceFactory(user=user)

        existing = EventRecordFactory(
            mapping=data_source,
            category="sleep",
            type_="sleep_session",
            start_datetime=self._dt(20, 56),
            end_datetime=self._dt(21, 26),
        )
        SleepDetailsFactory(
            event_record=existing,
            sleep_deep_minutes=0,
            sleep_light_minutes=8,
            sleep_rem_minutes=0,
            sleep_awake_minutes=22,
            sleep_total_duration_minutes=8,
            sleep_time_in_bed_minutes=30,
        )

        record = self._record(data_source, self._dt(22, 25), self._dt(7, 40, day=22))
        detail = self._detail(record.id, deep=90, light=200, rem=80, awake=30, in_bed=430)

        result = event_record_service.create_or_merge_sleep(db, user.id, record, detail, self.THRESHOLD)

        db.refresh(result)
        d = result.detail
        assert d.sleep_deep_minutes == 90  # 0 + 90
        assert d.sleep_light_minutes == 208  # 8 + 200
        assert d.sleep_rem_minutes == 80  # 0 + 80
        assert d.sleep_awake_minutes == 52  # 22 + 30
        assert d.sleep_total_duration_minutes == 378  # 8 + 370

    def test_merge_calculates_weighted_efficiency(self, db: Session) -> None:
        """Efficiency is a time-in-bed weighted average of both sessions."""
        user = UserFactory()
        data_source = DataSourceFactory(user=user)

        existing = EventRecordFactory(
            mapping=data_source,
            category="sleep",
            type_="sleep_session",
            start_datetime=self._dt(20, 56),
            end_datetime=self._dt(21, 26),
        )
        SleepDetailsFactory(
            event_record=existing,
            sleep_deep_minutes=0,
            sleep_light_minutes=8,
            sleep_rem_minutes=0,
            sleep_awake_minutes=22,
            sleep_total_duration_minutes=8,
            sleep_time_in_bed_minutes=30,
        )

        record = self._record(data_source, self._dt(22, 25), self._dt(7, 40, day=22))
        # 80% efficiency, 430 min in bed
        detail = self._detail(record.id, in_bed=430, efficiency="80.00")
        # Existing: 27% efficiency, 30 min in bed
        # existing detail created without efficiency — add manually
        existing.detail.sleep_efficiency_score = Decimal("27.00")
        db.flush()

        result = event_record_service.create_or_merge_sleep(db, user.id, record, detail, self.THRESHOLD)

        db.refresh(result)
        # (27*30 + 80*430) / 460 = (810 + 34400) / 460 = 35210 / 460 ≈ 76.54
        expected = round((27 * 30 + 80 * 430) / 460, 2)
        assert result.detail.sleep_efficiency_score == Decimal(str(expected))

    def test_old_record_deleted_after_merge(self, db: Session) -> None:
        """The adjacent record is deleted after merging."""
        user = UserFactory()
        data_source = DataSourceFactory(user=user)

        existing = EventRecordFactory(
            mapping=data_source,
            category="sleep",
            type_="sleep_session",
            start_datetime=self._dt(20, 56),
            end_datetime=self._dt(21, 26),
        )
        SleepDetailsFactory(event_record=existing)
        old_id = existing.id

        record = self._record(data_source, self._dt(22, 25), self._dt(7, 40, day=22))
        detail = self._detail(record.id)

        event_record_service.create_or_merge_sleep(db, user.id, record, detail, self.THRESHOLD)

        assert event_record_service.get(db, old_id) is None

    def test_adjacent_outside_threshold_not_merged(self, db: Session) -> None:
        """Sessions further apart than threshold create two separate records."""
        user = UserFactory()
        data_source = DataSourceFactory(user=user)

        existing = EventRecordFactory(
            mapping=data_source,
            category="sleep",
            type_="sleep_session",
            start_datetime=self._dt(1, 0),
            end_datetime=self._dt(8, 0),
        )
        SleepDetailsFactory(event_record=existing)

        # New session starts 3 hours after existing ends — beyond 120-min threshold
        record = self._record(data_source, self._dt(11, 0), self._dt(12, 0))
        detail = self._detail(record.id)

        result = event_record_service.create_or_merge_sleep(db, user.id, record, detail, self.THRESHOLD)

        assert result.id == record.id
        assert event_record_service.get(db, existing.id) is not None

    def test_different_user_adjacent_not_merged(self, db: Session) -> None:
        """Adjacent session belonging to a different user is never merged."""
        user1 = UserFactory(email="user1@example.com")
        user2 = UserFactory(email="user2@example.com")
        ds1 = DataSourceFactory(user=user1)
        ds2 = DataSourceFactory(user=user2)

        other_user_record = EventRecordFactory(
            mapping=ds2,
            category="sleep",
            type_="sleep_session",
            start_datetime=self._dt(20, 56),
            end_datetime=self._dt(21, 26),
        )
        SleepDetailsFactory(event_record=other_user_record)

        record = self._record(ds1, self._dt(22, 25), self._dt(7, 40, day=22))
        detail = self._detail(record.id)

        result = event_record_service.create_or_merge_sleep(db, user1.id, record, detail, self.THRESHOLD)

        assert result.id == record.id
        assert event_record_service.get(db, other_user_record.id) is not None

    def test_is_nap_false_when_only_one_is_nap(self, db: Session) -> None:
        """Merged session is not a nap unless both sessions are naps."""
        user = UserFactory()
        data_source = DataSourceFactory(user=user)

        existing = EventRecordFactory(
            mapping=data_source,
            category="sleep",
            type_="sleep_session",
            start_datetime=self._dt(20, 56),
            end_datetime=self._dt(21, 26),
        )
        SleepDetailsFactory(event_record=existing, is_nap=True)

        record = self._record(data_source, self._dt(22, 25), self._dt(7, 40, day=22))
        detail = self._detail(record.id, is_nap=False)

        result = event_record_service.create_or_merge_sleep(db, user.id, record, detail, self.THRESHOLD)

        db.refresh(result)
        assert result.detail.is_nap is False

    def test_is_nap_true_when_both_are_naps(self, db: Session) -> None:
        """Merged session is a nap when both sessions are naps."""
        user = UserFactory()
        data_source = DataSourceFactory(user=user)

        existing = EventRecordFactory(
            mapping=data_source,
            category="sleep",
            type_="sleep_session",
            start_datetime=self._dt(13, 0),
            end_datetime=self._dt(13, 20),
        )
        SleepDetailsFactory(event_record=existing, is_nap=True)

        record = self._record(data_source, self._dt(14, 30), self._dt(14, 50))
        detail = self._detail(record.id, is_nap=True)

        result = event_record_service.create_or_merge_sleep(db, user.id, record, detail, self.THRESHOLD)

        db.refresh(result)
        assert result.detail.is_nap is True

    def test_same_user_different_source_not_merged(self, db: Session) -> None:
        """Sessions from different data sources for the same user are never merged."""
        user = UserFactory()
        ds_oura = DataSourceFactory(user=user, source="oura")
        ds_garmin = DataSourceFactory(user=user, source="garmin")

        existing = EventRecordFactory(
            mapping=ds_oura,
            category="sleep",
            type_="sleep_session",
            start_datetime=self._dt(20, 56),
            end_datetime=self._dt(21, 26),
            duration_seconds=1800,
        )
        SleepDetailsFactory(event_record=existing)

        # Garmin record within threshold of the existing Oura record
        garmin_record = EventRecordCreate(
            id=uuid4(),
            category="sleep",
            type="sleep_session",
            source_name="garmin",
            source="garmin",
            user_id=user.id,
            data_source_id=ds_garmin.id,
            start_datetime=self._dt(22, 25),
            end_datetime=self._dt(7, 40, day=22),
            duration_seconds=int((self._dt(7, 40, day=22) - self._dt(22, 25)).total_seconds()),
        )
        detail = self._detail(garmin_record.id)

        result = event_record_service.create_or_merge_sleep(db, user.id, garmin_record, detail, self.THRESHOLD)

        assert result.id == garmin_record.id
        assert event_record_service.get(db, existing.id) is not None

    def test_overlapping_sessions_handled_safely(self, db: Session) -> None:
        """A new session fully contained within an existing one updates the detail without data loss."""
        user = UserFactory()
        data_source = DataSourceFactory(user=user)

        existing = EventRecordFactory(
            mapping=data_source,
            category="sleep",
            type_="sleep_session",
            start_datetime=self._dt(1, 0),
            end_datetime=self._dt(8, 0),
            duration_seconds=7 * 3600,
        )
        SleepDetailsFactory(
            event_record=existing,
            sleep_deep_minutes=60,
            sleep_light_minutes=180,
            sleep_rem_minutes=60,
            sleep_awake_minutes=30,
            sleep_total_duration_minutes=300,
            sleep_time_in_bed_minutes=330,
        )

        # New record is fully contained within existing: 2:00–7:00
        record = self._record(data_source, self._dt(2, 0), self._dt(7, 0))
        detail = self._detail(record.id, deep=30, light=150, rem=50, awake=20, in_bed=250)

        result = event_record_service.create_or_merge_sleep(db, user.id, record, detail, self.THRESHOLD)

        # Merged window equals the existing (new is contained within it)
        assert result.start_datetime == self._dt(1, 0)
        assert result.end_datetime == self._dt(8, 0)
        # Detail must be present — no silent data loss
        db.refresh(result)
        assert result.detail is not None

    def test_merge_concatenates_sleep_stages(self, db: Session) -> None:
        """Sleep stages from both sessions are concatenated and sorted."""
        user = UserFactory()
        data_source = DataSourceFactory(user=user)

        stage_early = {
            "stage": "light",
            "start_time": self._dt(20, 56).isoformat(),
            "end_time": self._dt(21, 26).isoformat(),
        }
        existing = EventRecordFactory(
            mapping=data_source,
            category="sleep",
            type_="sleep_session",
            start_datetime=self._dt(20, 56),
            end_datetime=self._dt(21, 26),
        )
        SleepDetailsFactory(
            event_record=existing,
            sleep_stages=[stage_early],
        )

        stage_late = SleepStage(
            stage="deep",
            start_time=self._dt(22, 30),
            end_time=self._dt(23, 30),
        )
        record = self._record(data_source, self._dt(22, 25), self._dt(7, 40, day=22))
        detail = self._detail(record.id)
        detail = detail.model_copy(update={"sleep_stages": [stage_late]})

        result = event_record_service.create_or_merge_sleep(db, user.id, record, detail, self.THRESHOLD)

        db.refresh(result)
        stages = result.detail.sleep_stages
        assert stages is not None
        assert len(stages) == 2
        # Stages should be sorted by start_time (early first)
        assert stages[0]["stage"] == "light"
        assert stages[1]["stage"] == "deep"


class TestGetSleepSessions:
    """Test get_sleep_sessions response fields."""

    def test_returns_sleep_duration_and_time_in_bed_when_details_present(self, db: Session) -> None:
        """sleep_duration_seconds should come from sleep_total_duration_minutes; duration_seconds stays time-in-bed."""
        user = UserFactory()
        mapping = DataSourceFactory(user=user, source="oura")
        start = datetime(2026, 4, 10, 23, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 11, 7, 0, tzinfo=timezone.utc)  # 8h in bed = 28800s
        record = EventRecordFactory(
            mapping=mapping,
            category="sleep",
            type_="sleep",
            start_datetime=start,
            end_datetime=end,
            duration_seconds=28800,
        )
        SleepDetailsFactory(
            event_record=record,
            sleep_total_duration_minutes=450,  # 7h30m of actual sleep
            sleep_awake_minutes=30,
        )

        params = EventRecordQueryParams(
            start_datetime=datetime(2026, 4, 1, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 4, 30, tzinfo=timezone.utc),
        )
        response = event_record_service.get_sleep_sessions(db, user.id, params)

        session = next(s for s in response.data if s.id == record.id)
        assert session.duration_seconds == 28800  # time in bed (unchanged)
        assert session.sleep_duration_seconds == 450 * 60  # actual sleep

    def test_sleep_duration_none_when_details_missing(self, db: Session) -> None:
        """sleep_duration_seconds should be None if SleepDetails has no total duration."""
        user = UserFactory()
        mapping = DataSourceFactory(user=user, source="oura")
        record = EventRecordFactory(
            mapping=mapping,
            category="sleep",
            type_="sleep",
            duration_seconds=28800,
        )

        params = EventRecordQueryParams(
            start_datetime=datetime(2026, 4, 1, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 4, 30, tzinfo=timezone.utc),
        )
        response = event_record_service.get_sleep_sessions(db, user.id, params)

        session = next(s for s in response.data if s.id == record.id)
        assert session.duration_seconds == 28800
        assert session.sleep_duration_seconds is None
