"""
Tests for UserConnectionService.

Tests cover:
- Getting active connection count in date range
- Creating user connections
- Updating user connections
- Managing connection status
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.schemas import UserConnectionCreate, UserConnectionUpdate
from app.schemas.oauth import ConnectionStatus
from app.services.user_connection_service import user_connection_service
from _tests.factories import UserConnectionFactory, UserFactory


class TestUserConnectionServiceGetActiveCountInRange:
    """Test counting active connections in date range."""

    def test_get_active_count_in_range_with_active_connections(self, db: Session) -> None:
        """Should count active connections created within date range."""
        # Arrange
        user = UserFactory()
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)

        # Create connections at different times with different statuses
        UserConnectionFactory(
            user=user,
            provider="garmin",
            status=ConnectionStatus.ACTIVE,
            created_at=two_weeks_ago,
        )  # Before range
        UserConnectionFactory(
            user=user,
            provider="polar",
            status=ConnectionStatus.ACTIVE,
            created_at=week_ago + timedelta(days=1),
        )  # In range
        UserConnectionFactory(
            user=user,
            provider="suunto",
            status=ConnectionStatus.ACTIVE,
            created_at=now - timedelta(days=1),
        )  # In range
        UserConnectionFactory(
            user=user,
            provider="strava",
            status=ConnectionStatus.REVOKED,
            created_at=now - timedelta(hours=1),
        )  # In range but not active

        # Act
        count = user_connection_service.get_active_count_in_range(db, week_ago, now)

        # Assert
        # Should count only the 2 active connections within the range
        assert count == 2

    def test_get_active_count_in_range_excludes_inactive_status(self, db: Session) -> None:
        """Should exclude connections with inactive status."""
        # Arrange
        user = UserFactory()
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)

        # Create connections with different statuses
        UserConnectionFactory(
            user=user,
            provider="garmin",
            status=ConnectionStatus.ACTIVE,
            created_at=now - timedelta(days=1),
        )
        UserConnectionFactory(
            user=user,
            provider="polar",
            status=ConnectionStatus.EXPIRED,
            created_at=now - timedelta(days=2),
        )
        UserConnectionFactory(
            user=user,
            provider="suunto",
            status=ConnectionStatus.REVOKED,
            created_at=now - timedelta(days=3),
        )

        # Act
        count = user_connection_service.get_active_count_in_range(db, week_ago, now)

        # Assert
        # Only ACTIVE status should be counted
        assert count == 1

    def test_get_active_count_in_range_empty_result(self, db: Session) -> None:
        """Should return 0 when no active connections in range."""
        # Arrange
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=7)
        far_future = future + timedelta(days=7)

        UserConnectionFactory()  # Created now, outside future range

        # Act
        count = user_connection_service.get_active_count_in_range(db, future, far_future)

        # Assert
        assert count == 0

    def test_get_active_count_in_range_boundary_inclusive(self, db: Session) -> None:
        """Should include connections at start boundary but exclude end boundary (half-open interval)."""
        # Arrange
        user = UserFactory()
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 2, 1, 0, 0, 0, tzinfo=timezone.utc)  # End is exclusive

        # Create connections at boundaries
        UserConnectionFactory(
            user=user,
            provider="garmin",
            status=ConnectionStatus.ACTIVE,
            created_at=start,
        )  # At start (included)
        UserConnectionFactory(
            user=user,
            provider="polar",
            status=ConnectionStatus.ACTIVE,
            created_at=datetime(2024, 1, 31, 23, 59, 59, tzinfo=timezone.utc),
        )  # Just before end (included)
        UserConnectionFactory(
            user=user,
            provider="suunto",
            status=ConnectionStatus.ACTIVE,
            created_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        )  # Middle

        # Act
        count = user_connection_service.get_active_count_in_range(db, start, end)

        # Assert
        assert count == 3


class TestUserConnectionServiceCreate:
    """Test creating user connections."""

    def test_create_user_connection_basic(self, db: Session) -> None:
        """Should create user connection with all required fields."""
        # Arrange
        user = UserFactory()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=30)

        connection_data = UserConnectionCreate(
            user_id=user.id,
            provider="garmin",
            provider_user_id="garmin_user_123",
            provider_username="athlete_123",
            access_token="access_token_abc",
            refresh_token="refresh_token_xyz",
            token_expires_at=expires_at,
            scope="read_all",
            status=ConnectionStatus.ACTIVE,
        )

        # Act
        connection = user_connection_service.create(db, connection_data)

        # Assert
        assert connection.id is not None
        assert connection.user_id == user.id
        assert connection.provider == "garmin"
        assert connection.provider_user_id == "garmin_user_123"
        assert connection.status == ConnectionStatus.ACTIVE
        assert connection.created_at is not None
        assert connection.updated_at is not None

    def test_create_user_connection_generates_id_and_timestamps(self, db: Session) -> None:
        """Should auto-generate ID and timestamps."""
        # Arrange
        user = UserFactory()
        connection_data = UserConnectionCreate(
            user_id=user.id,
            provider="polar",
            provider_user_id="polar_123",
            access_token="token",
            token_expires_at=datetime(2025, 12, 31, tzinfo=timezone.utc),
            status=ConnectionStatus.ACTIVE,
        )

        # Act
        connection = user_connection_service.create(db, connection_data)

        # Assert
        assert connection.id is not None
        assert connection.created_at is not None
        assert connection.updated_at is not None
        # Verify timestamps are recent
        assert (datetime.now(timezone.utc) - connection.created_at).total_seconds() < 60

    def test_create_user_connection_persists_to_database(self, db: Session) -> None:
        """Should persist connection to database."""
        # Arrange
        user = UserFactory()
        connection_data = UserConnectionCreate(
            user_id=user.id,
            provider="suunto",
            provider_user_id="suunto_123",
            access_token="token",
            token_expires_at=datetime(2025, 12, 31, tzinfo=timezone.utc),
            status=ConnectionStatus.ACTIVE,
        )

        # Act
        connection = user_connection_service.create(db, connection_data)

        # Assert - verify in database
        db_connection = user_connection_service.get(db, connection.id)
        assert db_connection is not None
        assert db_connection.provider == "suunto"


class TestUserConnectionServiceUpdate:
    """Test updating user connections."""

    def test_update_user_connection_status(self, db: Session) -> None:
        """Should update connection status."""
        # Arrange
        connection = UserConnectionFactory(status=ConnectionStatus.ACTIVE)
        update_data = UserConnectionUpdate(status=ConnectionStatus.REVOKED)

        # Act
        updated = user_connection_service.update(db, connection.id, update_data)

        # Assert
        assert updated is not None
        assert updated.status == ConnectionStatus.REVOKED
        assert updated.updated_at >= connection.updated_at

    def test_update_user_connection_tokens(self, db: Session) -> None:
        """Should update access and refresh tokens."""
        # Arrange
        connection = UserConnectionFactory()
        now = datetime.now(timezone.utc)
        new_expires = now + timedelta(days=60)

        update_data = UserConnectionUpdate(
            access_token="new_access_token",
            refresh_token="new_refresh_token",
            token_expires_at=new_expires,
        )

        # Act
        updated = user_connection_service.update(db, connection.id, update_data)

        # Assert
        assert updated is not None
        assert updated.access_token == "new_access_token"
        assert updated.refresh_token == "new_refresh_token"
        assert updated.token_expires_at == new_expires

    def test_update_user_connection_last_synced_at(self, db: Session) -> None:
        """Should update last_synced_at timestamp."""
        # Arrange
        connection = UserConnectionFactory(last_synced_at=None)
        now = datetime.now(timezone.utc)

        update_data = UserConnectionUpdate(last_synced_at=now)

        # Act
        updated = user_connection_service.update(db, connection.id, update_data)

        # Assert
        assert updated is not None
        assert updated.last_synced_at is not None
        assert (now - updated.last_synced_at).total_seconds() < 1

    def test_update_user_connection_sets_updated_at(self, db: Session) -> None:
        """Should automatically update updated_at timestamp."""
        # Arrange
        connection = UserConnectionFactory()
        original_updated_at = connection.updated_at

        update_data = UserConnectionUpdate(provider_username="new_username")

        # Act
        updated = user_connection_service.update(db, connection.id, update_data)

        # Assert
        assert updated is not None
        assert updated.updated_at > original_updated_at

    def test_update_nonexistent_connection_returns_none(self, db: Session) -> None:
        """Should return None when updating non-existent connection."""
        # Arrange
        fake_id = uuid4()
        update_data = UserConnectionUpdate(status=ConnectionStatus.REVOKED)

        # Act
        result = user_connection_service.update(db, fake_id, update_data, raise_404=False)

        # Assert
        assert result is None

    def test_update_user_connection_partial_update(self, db: Session) -> None:
        """Should update only specified fields."""
        # Arrange
        connection = UserConnectionFactory(
            provider_username="original_username",
            access_token="original_token",
            status=ConnectionStatus.ACTIVE,
        )

        update_data = UserConnectionUpdate(provider_username="updated_username")

        # Act
        updated = user_connection_service.update(db, connection.id, update_data)

        # Assert
        assert updated is not None
        assert updated.provider_username == "updated_username"
        assert updated.access_token == "original_token"  # Unchanged
        assert updated.status == ConnectionStatus.ACTIVE  # Unchanged


class TestUserConnectionServiceGet:
    """Test getting user connections."""

    def test_get_existing_connection(self, db: Session) -> None:
        """Should retrieve existing connection by ID."""
        # Arrange
        connection = UserConnectionFactory(provider="garmin")

        # Act
        retrieved = user_connection_service.get(db, connection.id)

        # Assert
        assert retrieved is not None
        assert retrieved.id == connection.id
        assert retrieved.provider == "garmin"

    def test_get_nonexistent_connection_returns_none(self, db: Session) -> None:
        """Should return None for non-existent connection."""
        # Arrange
        fake_id = uuid4()

        # Act
        result = user_connection_service.get(db, fake_id)

        # Assert
        assert result is None


class TestUserConnectionServiceDelete:
    """Test deleting user connections."""

    def test_delete_existing_connection(self, db: Session) -> None:
        """Should delete existing connection."""
        # Arrange
        connection = UserConnectionFactory()
        connection_id = connection.id

        # Act
        user_connection_service.delete(db, connection_id)

        # Assert
        result = user_connection_service.get(db, connection_id)
        assert result is None

    def test_delete_nonexistent_connection(self, db: Session) -> None:
        """Should handle deleting non-existent connection gracefully."""
        # Arrange
        fake_id = uuid4()

        # Act & Assert - should not raise error
        user_connection_service.delete(db, fake_id, raise_404=False)


class TestUserConnectionServiceConnectionStatus:
    """Test connection status management."""

    def test_create_connection_with_different_statuses(self, db: Session) -> None:
        """Should create connections with different status values."""
        # Arrange
        user = UserFactory()

        # Act & Assert
        providers = ["garmin", "polar", "suunto"]
        for status, provider in zip(
            [ConnectionStatus.ACTIVE, ConnectionStatus.REVOKED, ConnectionStatus.EXPIRED],
            providers,
        ):
            connection = UserConnectionFactory(user=user, provider=provider, status=status)
            assert connection.status == status

    def test_update_connection_status_transitions(self, db: Session) -> None:
        """Should handle status transitions."""
        # Arrange
        connection = UserConnectionFactory(status=ConnectionStatus.ACTIVE)

        # Act - transition from CONNECTED to REVOKED
        updated = user_connection_service.update(
            db,
            connection.id,
            UserConnectionUpdate(status=ConnectionStatus.REVOKED),
        )

        # Assert
        assert updated is not None
        assert updated.status == ConnectionStatus.REVOKED

        # Act - transition from REVOKED back to CONNECTED
        updated2 = user_connection_service.update(
            db,
            connection.id,
            UserConnectionUpdate(status=ConnectionStatus.ACTIVE),
        )

        # Assert
        assert updated2 is not None
        assert updated2.status == ConnectionStatus.ACTIVE
