"""
Tests for SystemInfoService.

Tests cover:
- Getting system dashboard information
- Aggregating metrics from multiple services

Note: the total data-points count is served approximately (planner statistics / cache) rather than
an exact ``COUNT(*)``, so it is only asserted to be a valid non-negative integer.
"""

from sqlalchemy.orm import Session

from app.services.system_info_service import system_info_service
from tests.factories import (
    DataPointSeriesFactory,
    DataSourceFactory,
    EventRecordFactory,
    SeriesTypeDefinitionFactory,
    UserConnectionFactory,
    UserFactory,
)


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

        assert hasattr(info.total_users, "count")
        assert hasattr(info.active_conn, "count")
        assert hasattr(info.data_points, "count")
        assert isinstance(info.data_points.count, int)

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
        from app.schemas.auth import ConnectionStatus

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

    def test_get_system_info_data_points_count_is_valid_int(self, db: Session) -> None:
        """The data-points count is approximate/cached; assert only that it is a non-negative int."""
        # Arrange
        mapping = DataSourceFactory()
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        for _ in range(5):
            DataPointSeriesFactory(mapping=mapping, series_type=series_type)

        # Act
        info = system_info_service.get_system_info(db)

        # Assert
        assert isinstance(info.data_points.count, int)
        assert info.data_points.count >= 0

    def test_get_system_info_event_records(self, db: Session) -> None:
        """Should report event-record totals with a per-category breakdown."""
        # Arrange
        initial = system_info_service.get_system_info(db).event_records
        mapping = DataSourceFactory()
        EventRecordFactory(mapping=mapping, category="workout", type_="running")
        EventRecordFactory(mapping=mapping, category="workout", type_="cycling")
        EventRecordFactory(mapping=mapping, category="sleep", type_=None)

        # Act
        event_records = system_info_service.get_system_info(db).event_records

        # Assert
        assert event_records.workouts == initial.workouts + 2
        assert event_records.sleep == initial.sleep + 1
        assert event_records.count == initial.count + 3
        assert isinstance(event_records.menstrual_cycles, int)

    def test_get_system_info_connections_coverage(self, db: Session) -> None:
        """Should include connections coverage in the response."""
        # Act
        info = system_info_service.get_system_info(db)

        # Assert
        assert hasattr(info.connections_coverage, "users_with_active")
        assert hasattr(info.connections_coverage, "users_with_multi_active")
        assert isinstance(info.connections_coverage.top_providers, list)

    def test_get_system_info_empty_database(self, db: Session) -> None:
        """Should handle empty database gracefully."""
        # Act
        info = system_info_service.get_system_info(db)

        # Assert
        assert info.total_users.count >= 0
        assert info.active_conn.count >= 0
        assert info.data_points.count >= 0
