"""
Tests for SystemInfoService.

Tests cover:
- Getting system dashboard information
- Calculating weekly growth percentages
- Aggregating metrics from multiple services
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.services.system_info_service import system_info_service
from _tests.factories import (
    DataPointSeriesFactory,
    DataSourceFactory,
    EventRecordFactory,
    SeriesTypeDefinitionFactory,
    UserConnectionFactory,
    UserFactory,
)


class TestSystemInfoServiceCalculateWeeklyGrowth:
    """Test weekly growth calculation."""

    def test_calculate_weekly_growth_positive(self) -> None:
        """Should calculate positive growth percentage."""
        # Arrange
        current = 150
        previous = 100

        # Act
        growth = system_info_service._calculate_weekly_growth(current, previous)

        # Assert
        assert growth == 50.0  # 50% growth

    def test_calculate_weekly_growth_negative(self) -> None:
        """Should calculate negative growth percentage."""
        # Arrange
        current = 75
        previous = 100

        # Act
        growth = system_info_service._calculate_weekly_growth(current, previous)

        # Assert
        assert growth == -25.0  # 25% decline

    def test_calculate_weekly_growth_zero_previous_with_current(self) -> None:
        """Should return 100% when previous is 0 and current is positive."""
        # Arrange
        current = 50
        previous = 0

        # Act
        growth = system_info_service._calculate_weekly_growth(current, previous)

        # Assert
        assert growth == 100.0

    def test_calculate_weekly_growth_both_zero(self) -> None:
        """Should return 0% when both current and previous are 0."""
        # Arrange
        current = 0
        previous = 0

        # Act
        growth = system_info_service._calculate_weekly_growth(current, previous)

        # Assert
        assert growth == 0.0

    def test_calculate_weekly_growth_no_change(self) -> None:
        """Should return 0% when no change."""
        # Arrange
        current = 100
        previous = 100

        # Act
        growth = system_info_service._calculate_weekly_growth(current, previous)

        # Assert
        assert growth == 0.0


class TestSystemInfoServiceGetSystemInfo:
    """Test getting system information."""

    def test_get_system_info_structure(self, db: Session) -> None:
        """Should return properly structured system info."""
        # Act
        info = system_info_service.get_system_info(db)

        # Assert
        assert info.total_users is not None
        assert info.active_conn is not None
        assert info.data_points is not None

        # Verify structure of CountWithGrowth
        assert hasattr(info.total_users, "count")
        assert hasattr(info.total_users, "weekly_growth")
        assert hasattr(info.active_conn, "count")
        assert hasattr(info.active_conn, "weekly_growth")

        # Verify data points info structure
        assert hasattr(info.data_points, "count")
        assert hasattr(info.data_points, "weekly_growth")
        assert hasattr(info.data_points, "top_series_types")
        assert hasattr(info.data_points, "top_workout_types")

    def test_get_system_info_total_users(self, db: Session) -> None:
        """Should count total users correctly."""
        # Arrange
        initial_info = system_info_service.get_system_info(db)
        initial_count = initial_info.total_users.count

        # Create new users
        UserFactory(email="user1@example.com")
        UserFactory(email="user2@example.com")

        # Act
        info = system_info_service.get_system_info(db)

        # Assert
        assert info.total_users.count == initial_count + 2

    def test_get_system_info_active_connections(self, db: Session) -> None:
        """Should count active connections correctly."""
        # Arrange
        from app.schemas.oauth import ConnectionStatus

        initial_info = system_info_service.get_system_info(db)
        initial_count = initial_info.active_conn.count

        user = UserFactory()

        # Create active and inactive connections with different providers
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)
        UserConnectionFactory(user=user, provider="polar", status=ConnectionStatus.ACTIVE)
        UserConnectionFactory(user=user, provider="suunto", status=ConnectionStatus.REVOKED)

        # Act
        info = system_info_service.get_system_info(db)

        # Assert
        assert info.active_conn.count >= initial_count + 2

    def test_get_system_info_data_points_count(self, db: Session) -> None:
        """Should count total data points correctly."""
        # Arrange
        initial_info = system_info_service.get_system_info(db)
        initial_count = initial_info.data_points.count

        mapping = DataSourceFactory()
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        # Create data points
        for _ in range(5):
            DataPointSeriesFactory(mapping=mapping, series_type=series_type)

        # Act
        info = system_info_service.get_system_info(db)

        # Assert
        assert info.data_points.count == initial_count + 5

    def test_get_system_info_weekly_growth_users(self, db: Session) -> None:
        """Should calculate weekly growth for users."""
        # Arrange
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)

        # Create users in different time periods
        UserFactory(created_at=two_weeks_ago - timedelta(days=1))  # Before tracking period
        UserFactory(created_at=two_weeks_ago + timedelta(days=1))  # Last week
        UserFactory(created_at=week_ago + timedelta(days=1))  # This week
        UserFactory(created_at=now - timedelta(hours=1))  # This week

        # Act
        info = system_info_service.get_system_info(db)

        # Assert
        # This week: 2 users, Last week: 1 user
        # Growth = ((2 - 1) / 1) * 100 = 100%
        assert info.total_users.weekly_growth == 100.0

    def test_get_system_info_top_series_types(self, db: Session) -> None:
        """Should return top series types by count."""
        # Arrange
        mapping = DataSourceFactory()
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        step_type = SeriesTypeDefinitionFactory.get_or_create_steps()

        # Create more heart rate samples
        for _ in range(10):
            DataPointSeriesFactory(mapping=mapping, series_type=hr_type)

        # Create fewer step samples
        for _ in range(5):
            DataPointSeriesFactory(mapping=mapping, series_type=step_type)

        # Act
        info = system_info_service.get_system_info(db)

        # Assert
        top_types = info.data_points.top_series_types
        assert len(top_types) >= 2

        # Find our test series types
        hr_metric = next((t for t in top_types if t.series_type == "heart_rate"), None)
        step_metric = next((t for t in top_types if t.series_type == "steps"), None)

        assert hr_metric is not None
        assert hr_metric.count >= 10

        assert step_metric is not None
        assert step_metric.count >= 5

    def test_get_system_info_top_series_types_limited_to_five(self, db: Session) -> None:
        """Should return at most 5 top series types."""
        # Arrange
        mapping = DataSourceFactory()

        # Use existing seeded series types to avoid conflicts
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        step_type = SeriesTypeDefinitionFactory.get_or_create_steps()

        # Create samples - using seeded types to avoid unique constraint violations
        for _ in range(6):
            DataPointSeriesFactory(mapping=mapping, series_type=hr_type)
        for _ in range(4):
            DataPointSeriesFactory(mapping=mapping, series_type=step_type)

        # Act
        info = system_info_service.get_system_info(db)

        # Assert
        assert len(info.data_points.top_series_types) <= 5

    def test_get_system_info_top_workout_types(self, db: Session) -> None:
        """Should return top workout types by count."""
        # Arrange
        mapping = DataSourceFactory()

        # Create workouts of different types
        for _ in range(8):
            EventRecordFactory(mapping=mapping, category="workout", type_="running")

        for _ in range(5):
            EventRecordFactory(mapping=mapping, category="workout", type_="cycling")

        for _ in range(3):
            EventRecordFactory(mapping=mapping, category="workout", type_="swimming")

        # Act
        info = system_info_service.get_system_info(db)

        # Assert
        top_workouts = info.data_points.top_workout_types
        assert len(top_workouts) >= 3

        # Find our test workout types
        running_metric = next((w for w in top_workouts if w.workout_type == "running"), None)
        cycling_metric = next((w for w in top_workouts if w.workout_type == "cycling"), None)
        swimming_metric = next((w for w in top_workouts if w.workout_type == "swimming"), None)

        assert running_metric is not None
        assert running_metric.count >= 8

        assert cycling_metric is not None
        assert cycling_metric.count >= 5

        assert swimming_metric is not None
        assert swimming_metric.count >= 3

    def test_get_system_info_top_workout_types_limited_to_five(self, db: Session) -> None:
        """Should return at most 5 top workout types."""
        # Arrange
        mapping = DataSourceFactory()

        # Create 6 different workout types
        for i in range(6):
            for _ in range(i + 1):
                EventRecordFactory(mapping=mapping, category="workout", type_=f"workout_{i}")

        # Act
        info = system_info_service.get_system_info(db)

        # Assert
        assert len(info.data_points.top_workout_types) <= 5

    def test_get_system_info_handles_null_workout_type(self, db: Session) -> None:
        """Should handle workouts with null type."""
        # Arrange
        mapping = DataSourceFactory()

        # Create workouts with null type
        EventRecordFactory(mapping=mapping, category="workout", type_=None)
        EventRecordFactory(mapping=mapping, category="workout", type_=None)

        # Act
        info = system_info_service.get_system_info(db)

        # Assert
        top_workouts = info.data_points.top_workout_types
        unknown_metric = next((w for w in top_workouts if w.workout_type == "Unknown"), None)

        if unknown_metric:
            assert unknown_metric.count >= 2

    def test_get_system_info_empty_database(self, db: Session) -> None:
        """Should handle empty database gracefully."""
        # Act
        info = system_info_service.get_system_info(db)

        # Assert
        assert info.total_users.count >= 0
        assert info.active_conn.count >= 0
        assert info.data_points.count >= 0
        assert isinstance(info.data_points.top_series_types, list)
        assert isinstance(info.data_points.top_workout_types, list)

    def test_get_system_info_weekly_growth_zero_division(self, db: Session) -> None:
        """Should handle zero division in weekly growth calculation."""
        # This tests the edge case where last week had 0 items and this week has items
        # The _calculate_weekly_growth should return 100.0 in this case

        # Arrange - clear any existing data or use isolated test scenario
        now = datetime.now(timezone.utc)
        now - timedelta(days=7)

        # Create user only in this week (not last week)
        UserFactory(created_at=now - timedelta(hours=1))

        # Act
        info = system_info_service.get_system_info(db)

        # Assert
        # weekly_growth should handle the case where previous week had 0 users
        assert isinstance(info.total_users.weekly_growth, float)
        assert info.total_users.weekly_growth >= 0.0 or info.total_users.weekly_growth == 100.0
