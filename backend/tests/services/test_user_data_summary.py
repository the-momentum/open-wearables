from uuid import uuid4

from sqlalchemy.orm import Session

from app.schemas.enums import ProviderName
from app.services.system_info_service import system_info_service
from tests.factories import (
    DataPointSeriesFactory,
    DataSourceFactory,
    EventRecordFactory,
    SeriesTypeDefinitionFactory,
    UserFactory,
)


class TestGetUserDataSummary:
    """Tests for SystemInfoService.get_user_data_summary."""

    def test_empty_user(self, db: Session) -> None:
        """User with no data returns all zeros."""
        user = UserFactory()
        result = system_info_service.get_user_data_summary(db, user.id)

        assert result.user_id == str(user.id)
        assert result.total_data_points == 0
        assert result.total_workouts == 0
        assert result.total_sleep_events == 0
        assert result.series_type_counts == {}
        assert result.workout_type_counts == {}
        assert result.by_provider == []

    def test_series_type_counts(self, db: Session) -> None:
        """Counts data points grouped by series type."""
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.APPLE)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()

        for _ in range(3):
            DataPointSeriesFactory(data_source=ds, series_type=hr_type)
        for _ in range(2):
            DataPointSeriesFactory(data_source=ds, series_type=steps_type)

        result = system_info_service.get_user_data_summary(db, user.id)

        assert result.total_data_points == 5
        assert result.series_type_counts["heart_rate"] == 3
        assert result.series_type_counts["steps"] == 2

    def test_workout_and_sleep_counts(self, db: Session) -> None:
        """Counts workouts and sleep events separately."""
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.GARMIN)

        for _ in range(4):
            EventRecordFactory(data_source=ds, category="workout", type="running")
        for _ in range(2):
            EventRecordFactory(data_source=ds, category="workout", type="cycling")
        for _ in range(3):
            EventRecordFactory(data_source=ds, category="sleep", type="sleep_session")

        result = system_info_service.get_user_data_summary(db, user.id)

        assert result.total_workouts == 6
        assert result.total_sleep_events == 3
        assert result.workout_type_counts["running"] == 4
        assert result.workout_type_counts["cycling"] == 2

    def test_multi_provider_breakdown(self, db: Session) -> None:
        """Breaks down counts by provider."""
        user = UserFactory()
        apple_ds = DataSourceFactory(user=user, provider=ProviderName.APPLE)
        garmin_ds = DataSourceFactory(user=user, provider=ProviderName.GARMIN)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        for _ in range(5):
            DataPointSeriesFactory(data_source=apple_ds, series_type=hr_type)
        for _ in range(3):
            DataPointSeriesFactory(data_source=garmin_ds, series_type=hr_type)

        EventRecordFactory(data_source=apple_ds, category="workout", type="running")
        EventRecordFactory(data_source=garmin_ds, category="sleep", type="sleep_session")

        result = system_info_service.get_user_data_summary(db, user.id)

        assert len(result.by_provider) == 2

        providers_by_name = {p.provider: p for p in result.by_provider}
        apple = providers_by_name[ProviderName.APPLE]
        garmin = providers_by_name[ProviderName.GARMIN]

        assert apple.data_points == 5
        assert apple.series_counts["heart_rate"] == 5
        assert apple.workout_count == 1
        assert apple.sleep_count == 0

        assert garmin.data_points == 3
        assert garmin.series_counts["heart_rate"] == 3
        assert garmin.workout_count == 0
        assert garmin.sleep_count == 1

    def test_does_not_include_other_users(self, db: Session) -> None:
        """Only counts data belonging to the requested user."""
        user_a = UserFactory()
        user_b = UserFactory()
        ds_a = DataSourceFactory(user=user_a, provider=ProviderName.APPLE)
        ds_b = DataSourceFactory(user=user_b, provider=ProviderName.APPLE)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        for _ in range(3):
            DataPointSeriesFactory(data_source=ds_a, series_type=hr_type)
        for _ in range(7):
            DataPointSeriesFactory(data_source=ds_b, series_type=hr_type)

        result = system_info_service.get_user_data_summary(db, user_a.id)
        assert result.total_data_points == 3

    def test_nonexistent_user(self, db: Session) -> None:
        """Returns empty summary for a user ID with no data."""
        result = system_info_service.get_user_data_summary(db, uuid4())
        assert result.total_data_points == 0
        assert result.by_provider == []

    def test_providers_sorted_by_total_records(self, db: Session) -> None:
        """Providers are sorted by total record count descending."""
        user = UserFactory()
        small_ds = DataSourceFactory(user=user, provider=ProviderName.OURA)
        big_ds = DataSourceFactory(user=user, provider=ProviderName.APPLE)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        DataPointSeriesFactory(data_source=small_ds, series_type=hr_type)
        for _ in range(10):
            DataPointSeriesFactory(data_source=big_ds, series_type=hr_type)

        result = system_info_service.get_user_data_summary(db, user.id)

        assert result.by_provider[0].provider == ProviderName.APPLE
        assert result.by_provider[1].provider == ProviderName.OURA
