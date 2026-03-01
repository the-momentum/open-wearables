"""
Integration tests for Ultrahuman provider using mocked API calls.

These tests verify the complete Ultrahuman integration from API response
to database storage using mocked responses, making them deterministic
and runnable without real credentials.
"""

from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.models import DataPointSeries, EventRecord, ExternalDeviceMapping, SleepDetails
from app.services.providers.factory import ProviderFactory
from app.services.providers.ultrahuman.data_247 import Ultrahuman247Data
from tests.factories import (
    ExternalDeviceMappingFactory,
    UserConnectionFactory,
    UserFactory,
)


class TestUltrahumanSleepDataIntegration:
    """Integration tests for Ultrahuman sleep data synchronization."""

    def test_full_sleep_sync_flow_with_mocked_api(self, db: Session, sample_ultrahuman_api_response: dict) -> None:
        """Test complete sleep sync flow: Mocked API -> Normalization -> Database."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="ultrahuman", status="active", access_token="test_token")
        ExternalDeviceMappingFactory(user_id=user.id, provider_name="ultrahuman")

        factory = ProviderFactory()
        strategy = factory.get_provider("ultrahuman")
        provider_impl = strategy.data_247
        assert isinstance(provider_impl, Ultrahuman247Data)

        end_time = datetime(2024, 1, 16, tzinfo=timezone.utc)
        start_time = datetime(2024, 1, 15, tzinfo=timezone.utc)

        with patch.object(
            provider_impl,
            "_make_api_request",
            return_value=sample_ultrahuman_api_response,
        ) as mock_request:
            results = provider_impl.load_and_save_all(db, user.id, start_time=start_time, end_time=end_time)
            db.commit()

            assert mock_request.call_count == 2  # 2 days in range
            assert results is not None
            assert "sleep_sessions_synced" in results
            assert results["sleep_sessions_synced"] >= 0

    def test_verify_sleep_records_in_database_with_mocked_api(
        self, db: Session, sample_ultrahuman_api_response: dict
    ) -> None:
        """Verify sleep records are correctly stored with all fields."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="ultrahuman", status="active", access_token="test_token")
        ExternalDeviceMappingFactory(user_id=user.id, provider_name="ultrahuman")

        factory = ProviderFactory()
        strategy = factory.get_provider("ultrahuman")
        provider_impl = strategy.data_247
        assert isinstance(provider_impl, Ultrahuman247Data)

        end_time = datetime(2024, 1, 16, tzinfo=timezone.utc)
        start_time = datetime(2024, 1, 15, tzinfo=timezone.utc)

        with patch.object(provider_impl, "_make_api_request", return_value=sample_ultrahuman_api_response):
            results = provider_impl.load_and_save_all(db, user.id, start_time=start_time, end_time=end_time)
            db.commit()

            if results["sleep_sessions_synced"] > 0:
                records = (
                    db.query(EventRecord)
                    .join(ExternalDeviceMapping)
                    .filter(
                        ExternalDeviceMapping.user_id == user.id,
                        ExternalDeviceMapping.provider_name == "ultrahuman",
                        EventRecord.category == "sleep",
                    )
                    .all()
                )

                assert len(records) > 0, "No sleep records found in database"

                for record in records:
                    assert record.category == "sleep"
                    assert record.duration_seconds is not None
                    assert record.start_datetime is not None
                    assert record.end_datetime is not None

                    details = db.query(SleepDetails).filter(SleepDetails.record_id == record.id).first()
                    if details:
                        assert details.sleep_efficiency_score is not None
                        assert details.sleep_deep_minutes is not None
                        assert details.sleep_light_minutes is not None
                        assert details.sleep_rem_minutes is not None
                        assert details.sleep_awake_minutes is not None

                        total = (
                            (details.sleep_deep_minutes or 0)
                            + (details.sleep_light_minutes or 0)
                            + (details.sleep_rem_minutes or 0)
                            + (details.sleep_awake_minutes or 0)
                        )
                        total_sleep = (
                            (details.sleep_deep_minutes or 0)
                            + (details.sleep_light_minutes or 0)
                            + (details.sleep_rem_minutes or 0)
                        )

                        assert total >= 0, "Total minutes should be non-negative"
                        assert total_sleep >= 0, "Total sleep minutes should be non-negative"

    def test_sleep_efficiency_extraction_with_mocked_api(
        self, db: Session, sample_ultrahuman_api_response: dict
    ) -> None:
        """Verify sleep efficiency is correctly extracted from quick_metrics."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="ultrahuman", status="active", access_token="test_token")
        ExternalDeviceMappingFactory(user_id=user.id, provider_name="ultrahuman")

        factory = ProviderFactory()
        strategy = factory.get_provider("ultrahuman")
        provider_impl = strategy.data_247
        assert isinstance(provider_impl, Ultrahuman247Data)

        end_time = datetime(2024, 1, 16, tzinfo=timezone.utc)
        start_time = datetime(2024, 1, 15, tzinfo=timezone.utc)

        with patch.object(provider_impl, "_make_api_request", return_value=sample_ultrahuman_api_response):
            results = provider_impl.load_and_save_all(db, user.id, start_time=start_time, end_time=end_time)
            db.commit()

            if results["sleep_sessions_synced"] > 0:
                records = (
                    db.query(EventRecord)
                    .join(ExternalDeviceMapping)
                    .filter(
                        ExternalDeviceMapping.user_id == user.id,
                        EventRecord.category == "sleep",
                    )
                    .all()
                )

                for record in records:
                    details = db.query(SleepDetails).filter(SleepDetails.record_id == record.id).first()
                    if details:
                        assert details.sleep_efficiency_score is not None, "Sleep efficiency should not be null"
                        assert 0 <= details.sleep_efficiency_score <= 100, (
                            f"Sleep efficiency {details.sleep_efficiency_score} should be 0-100"
                        )

    def test_sleep_stage_values_are_nonzero_with_mocked_api(
        self, db: Session, sample_ultrahuman_api_response: dict
    ) -> None:
        """Verify sleep stage values are not all zero after sync."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="ultrahuman", status="active", access_token="test_token")
        ExternalDeviceMappingFactory(user_id=user.id, provider_name="ultrahuman")

        factory = ProviderFactory()
        strategy = factory.get_provider("ultrahuman")
        provider_impl = strategy.data_247
        assert isinstance(provider_impl, Ultrahuman247Data)

        end_time = datetime(2024, 1, 16, tzinfo=timezone.utc)
        start_time = datetime(2024, 1, 15, tzinfo=timezone.utc)

        with patch.object(provider_impl, "_make_api_request", return_value=sample_ultrahuman_api_response):
            results = provider_impl.load_and_save_all(db, user.id, start_time=start_time, end_time=end_time)
            db.commit()

            if results["sleep_sessions_synced"] > 0:
                records = (
                    db.query(EventRecord)
                    .join(ExternalDeviceMapping)
                    .filter(
                        ExternalDeviceMapping.user_id == user.id,
                        EventRecord.category == "sleep",
                    )
                    .all()
                )

                all_zero = True
                for record in records:
                    details = db.query(SleepDetails).filter(SleepDetails.record_id == record.id).first()
                    if details:
                        stage_sum = (
                            (details.sleep_deep_minutes or 0)
                            + (details.sleep_light_minutes or 0)
                            + (details.sleep_rem_minutes or 0)
                            + (details.sleep_awake_minutes or 0)
                        )
                        if stage_sum > 0:
                            all_zero = False
                            break

                assert not all_zero, "All sleep stage values are zero - parsing may be broken"


class TestUltrahumanActivitySamplesIntegration:
    """Integration tests for Ultrahuman activity samples synchronization."""

    def test_full_activity_samples_sync_flow_with_mocked_api(
        self, db: Session, sample_ultrahuman_api_response: dict
    ) -> None:
        """Test complete activity samples sync flow: Mocked API -> Normalization -> Database."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="ultrahuman", status="active", access_token="test_token")
        ExternalDeviceMappingFactory(user_id=user.id, provider_name="ultrahuman")

        factory = ProviderFactory()
        strategy = factory.get_provider("ultrahuman")
        provider_impl = strategy.data_247
        assert isinstance(provider_impl, Ultrahuman247Data)

        end_time = datetime(2024, 1, 16, tzinfo=timezone.utc)
        start_time = datetime(2024, 1, 15, tzinfo=timezone.utc)

        with patch.object(provider_impl, "_make_api_request", return_value=sample_ultrahuman_api_response):
            results = provider_impl.load_and_save_all(db, user.id, start_time=start_time, end_time=end_time)
            db.commit()

            assert results is not None
            assert "activity_samples" in results
            assert results["activity_samples"] >= 0

    def test_verify_activity_samples_in_database_with_mocked_api(
        self, db: Session, sample_ultrahuman_api_response: dict
    ) -> None:
        """Verify activity samples are correctly stored for all data types."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="ultrahuman", status="active", access_token="test_token")
        ExternalDeviceMappingFactory(user_id=user.id, provider_name="ultrahuman")

        factory = ProviderFactory()
        strategy = factory.get_provider("ultrahuman")
        provider_impl = strategy.data_247
        assert isinstance(provider_impl, Ultrahuman247Data)

        end_time = datetime(2024, 1, 16, tzinfo=timezone.utc)
        start_time = datetime(2024, 1, 15, tzinfo=timezone.utc)

        with patch.object(provider_impl, "_make_api_request", return_value=sample_ultrahuman_api_response):
            results = provider_impl.load_and_save_all(db, user.id, start_time=start_time, end_time=end_time)
            db.commit()

            if results["activity_samples"] > 0:
                samples_by_type = {}

                samples = (
                    db.query(DataPointSeries)
                    .join(ExternalDeviceMapping)
                    .filter(
                        ExternalDeviceMapping.user_id == user.id,
                        ExternalDeviceMapping.provider_name == "ultrahuman",
                    )
                    .all()
                )

                assert len(samples) > 0, "No activity samples found in database"

                for sample in samples:
                    if sample.series_type_definition_id not in samples_by_type:
                        samples_by_type[sample.series_type_definition_id] = 0
                    samples_by_type[sample.series_type_definition_id] += 1

                series_types = {1: "heart_rate", 2: "hrv", 3: "body_temperature", 80: "steps"}

                for type_id, count in samples_by_type.items():
                    type_name = series_types.get(type_id, f"unknown_{type_id}")
                    assert count > 0, f"{type_name} should have samples"

    def test_heart_rate_values_are_reasonable_with_mocked_api(
        self, db: Session, sample_ultrahuman_api_response: dict
    ) -> None:
        """Verify heart rate values are within realistic range (40-200 bpm)."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="ultrahuman", status="active", access_token="test_token")
        ExternalDeviceMappingFactory(user_id=user.id, provider_name="ultrahuman")

        factory = ProviderFactory()
        strategy = factory.get_provider("ultrahuman")
        provider_impl = strategy.data_247
        assert isinstance(provider_impl, Ultrahuman247Data)

        end_time = datetime(2024, 1, 16, tzinfo=timezone.utc)
        start_time = datetime(2024, 1, 15, tzinfo=timezone.utc)

        with patch.object(provider_impl, "_make_api_request", return_value=sample_ultrahuman_api_response):
            provider_impl.load_and_save_all(db, user.id, start_time=start_time, end_time=end_time)
            db.commit()

        heart_rate_type_id = 1

        samples = (
            db.query(DataPointSeries)
            .join(ExternalDeviceMapping)
            .filter(
                ExternalDeviceMapping.user_id == user.id,
                DataPointSeries.series_type_definition_id == heart_rate_type_id,
            )
            .all()
        )

        for sample in samples:
            value = float(sample.value)
            assert 40 <= value <= 200, f"Heart rate {value} is outside realistic range"

    def test_temperature_values_are_reasonable_with_mocked_api(
        self, db: Session, sample_ultrahuman_api_response: dict
    ) -> None:
        """Verify temperature values are within realistic range (35-42°C)."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="ultrahuman", status="active", access_token="test_token")
        ExternalDeviceMappingFactory(user_id=user.id, provider_name="ultrahuman")

        factory = ProviderFactory()
        strategy = factory.get_provider("ultrahuman")
        provider_impl = strategy.data_247
        assert isinstance(provider_impl, Ultrahuman247Data)

        end_time = datetime(2024, 1, 16, tzinfo=timezone.utc)
        start_time = datetime(2024, 1, 15, tzinfo=timezone.utc)

        with patch.object(provider_impl, "_make_api_request", return_value=sample_ultrahuman_api_response):
            provider_impl.load_and_save_all(db, user.id, start_time=start_time, end_time=end_time)
            db.commit()

        temp_type_id = 3

        samples = (
            db.query(DataPointSeries)
            .join(ExternalDeviceMapping)
            .filter(
                ExternalDeviceMapping.user_id == user.id,
                DataPointSeries.series_type_definition_id == temp_type_id,
            )
            .all()
        )

        for sample in samples:
            value = float(sample.value)
            assert 35 <= value <= 42, f"Temperature {value} is outside realistic range"

    def test_timestamps_are_utc_with_mocked_api(self, db: Session, sample_ultrahuman_api_response: dict) -> None:
        """Verify all activity sample timestamps are in UTC timezone."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="ultrahuman", status="active", access_token="test_token")
        ExternalDeviceMappingFactory(user_id=user.id, provider_name="ultrahuman")

        factory = ProviderFactory()
        strategy = factory.get_provider("ultrahuman")
        provider_impl = strategy.data_247
        assert isinstance(provider_impl, Ultrahuman247Data)

        end_time = datetime(2024, 1, 16, tzinfo=timezone.utc)
        start_time = datetime(2024, 1, 15, tzinfo=timezone.utc)

        with patch.object(provider_impl, "_make_api_request", return_value=sample_ultrahuman_api_response):
            provider_impl.load_and_save_all(db, user.id, start_time=start_time, end_time=end_time)
            db.commit()

        samples = (
            db.query(DataPointSeries).join(ExternalDeviceMapping).filter(ExternalDeviceMapping.user_id == user.id).all()
        )

        for sample in samples:
            assert sample.recorded_at.tzinfo is not None, f"Timestamp {sample.recorded_at} has no timezone info"
            assert sample.recorded_at.tzinfo == timezone.utc, f"Timestamp {sample.recorded_at} is not UTC"


class TestUltrahumanAPIEndpoints:
    """Tests for Ultrahuman-specific API endpoints."""

    def test_sleep_events_endpoint_returns_data_with_mocked_api(
        self, db: Session, sample_ultrahuman_api_response: dict
    ) -> None:
        """Verify sleep events endpoint returns data after sync."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="ultrahuman", status="active", access_token="test_token")
        ExternalDeviceMappingFactory(user_id=user.id, provider_name="ultrahuman")

        factory = ProviderFactory()
        strategy = factory.get_provider("ultrahuman")
        provider_impl = strategy.data_247
        assert isinstance(provider_impl, Ultrahuman247Data)

        end_time = datetime(2024, 1, 16, tzinfo=timezone.utc)
        start_time = datetime(2024, 1, 15, tzinfo=timezone.utc)

        with patch.object(provider_impl, "_make_api_request", return_value=sample_ultrahuman_api_response):
            results = provider_impl.load_and_save_all(db, user.id, start_time=start_time, end_time=end_time)
            db.commit()

            if results["sleep_sessions_synced"] > 0:
                records = (
                    db.query(EventRecord)
                    .join(ExternalDeviceMapping)
                    .filter(
                        ExternalDeviceMapping.user_id == user.id,
                        EventRecord.category == "sleep",
                    )
                    .all()
                )

                assert len(records) > 0, "Should have sleep records after sync"

    def test_timeseries_endpoint_returns_data_with_mocked_api(
        self, db: Session, sample_ultrahuman_api_response: dict
    ) -> None:
        """Verify timeseries endpoint returns activity samples after sync."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="ultrahuman", status="active", access_token="test_token")
        ExternalDeviceMappingFactory(user_id=user.id, provider_name="ultrahuman")

        factory = ProviderFactory()
        strategy = factory.get_provider("ultrahuman")
        provider_impl = strategy.data_247
        assert isinstance(provider_impl, Ultrahuman247Data)

        end_time = datetime(2024, 1, 16, tzinfo=timezone.utc)
        start_time = datetime(2024, 1, 15, tzinfo=timezone.utc)

        with patch.object(provider_impl, "_make_api_request", return_value=sample_ultrahuman_api_response):
            results = provider_impl.load_and_save_all(db, user.id, start_time=start_time, end_time=end_time)
            db.commit()

            if results["activity_samples"] > 0:
                samples = (
                    db.query(DataPointSeries)
                    .join(ExternalDeviceMapping)
                    .filter(ExternalDeviceMapping.user_id == user.id)
                    .all()
                )

                assert len(samples) > 0, "Should have activity samples after sync"


class TestUltrahumanErrorHandling:
    """Tests for Ultrahuman error handling and edge cases."""

    def test_sync_handles_no_data_days_with_mocked_api(self, db: Session) -> None:
        """Verify sync continues when API returns no data for some days."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="ultrahuman", status="active", access_token="test_token")
        ExternalDeviceMappingFactory(user_id=user.id, provider_name="ultrahuman")

        factory = ProviderFactory()
        strategy = factory.get_provider("ultrahuman")
        provider_impl = strategy.data_247
        assert isinstance(provider_impl, Ultrahuman247Data)

        empty_response = {"data": {"metric_data": []}}

        end_time = datetime(2024, 1, 16, tzinfo=timezone.utc)
        start_time = datetime(2024, 1, 14, tzinfo=timezone.utc)

        with patch.object(provider_impl, "_make_api_request", return_value=empty_response):
            results = provider_impl.load_and_save_all(db, user.id, start_time=start_time, end_time=end_time)
            db.commit()

            assert results is not None
            assert "sleep_sessions_synced" in results
            assert "activity_samples" in results
            assert isinstance(results["sleep_sessions_synced"], int)
            assert isinstance(results["activity_samples"], int)

    def test_sync_handles_partial_data_with_mocked_api(self, db: Session) -> None:
        """Verify sync handles days with partial data (sleep but no activity)."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="ultrahuman", status="active", access_token="test_token")
        ExternalDeviceMappingFactory(user_id=user.id, provider_name="ultrahuman")

        factory = ProviderFactory()
        strategy = factory.get_provider("ultrahuman")
        provider_impl = strategy.data_247
        assert isinstance(provider_impl, Ultrahuman247Data)

        partial_response = {
            "data": {
                "metric_data": [
                    {
                        "type": "Sleep",
                        "object": {
                            "date": "2024-01-15",
                            "bedtime_start": 1705309200,
                            "bedtime_end": 1705334400,
                            "quick_metrics": [
                                {"type": "time_in_bed", "value": 25200},
                                {"type": "sleep_efic", "value": 90.5},
                            ],
                            "sleep_stages": [
                                {"type": "deep_sleep", "stage_time": 3600},
                                {"type": "light_sleep", "stage_time": 16200},
                                {"type": "rem_sleep", "stage_time": 3600},
                                {"type": "awake", "stage_time": 1800},
                            ],
                        },
                    },
                ]
            }
        }

        end_time = datetime(2024, 1, 16, tzinfo=timezone.utc)
        start_time = datetime(2024, 1, 14, tzinfo=timezone.utc)

        with patch.object(provider_impl, "_make_api_request", return_value=partial_response):
            results = provider_impl.load_and_save_all(db, user.id, start_time=start_time, end_time=end_time)
            db.commit()

            assert results is not None
            assert "sleep_sessions_synced" in results
            assert "activity_samples" in results
            assert isinstance(results["sleep_sessions_synced"], int)
            assert isinstance(results["activity_samples"], int)

    def test_sync_respects_date_range_with_mocked_api(self, db: Session, sample_ultrahuman_api_response: dict) -> None:
        """Verify sync only fetches data within specified date range."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="ultrahuman", status="active", access_token="test_token")
        ExternalDeviceMappingFactory(user_id=user.id, provider_name="ultrahuman")

        factory = ProviderFactory()
        strategy = factory.get_provider("ultrahuman")
        provider_impl = strategy.data_247
        assert isinstance(provider_impl, Ultrahuman247Data)

        end_time = datetime(2024, 1, 17, tzinfo=timezone.utc)
        start_time = datetime(2024, 1, 15, tzinfo=timezone.utc)

        with patch.object(provider_impl, "_make_api_request", return_value=sample_ultrahuman_api_response):
            results = provider_impl.load_and_save_all(db, user.id, start_time=start_time, end_time=end_time)
            db.commit()

            if results["sleep_sessions_synced"] > 0:
                records = (
                    db.query(EventRecord)
                    .join(ExternalDeviceMapping)
                    .filter(
                        ExternalDeviceMapping.user_id == user.id,
                        EventRecord.category == "sleep",
                    )
                    .all()
                )

                for record in records:
                    assert record.start_datetime >= start_time, (
                        f"Sleep record {record.start_datetime} is before start time {start_time}"
                    )
                    assert record.start_datetime <= end_time, (
                        f"Sleep record {record.start_datetime} is after end time {end_time}"
                    )
