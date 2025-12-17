"""
Tests for UserConnectionRepository.

Tests cover:
- CRUD operations (create, get, get_all, update, delete)
- Specialized query methods (get_by_user_and_provider, get_active_connection, etc.)
- Token management (update_tokens, mark_as_revoked)
- Status filtering and counting (get_active_count, get_active_count_in_range)
- Token expiration queries (get_expiring_tokens)
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import UserConnection
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.oauth import ConnectionStatus, UserConnectionCreate, UserConnectionUpdate
from app.tests.utils.factories import create_user, create_user_connection


class TestUserConnectionRepository:
    """Test suite for UserConnectionRepository."""

    @pytest.fixture
    def connection_repo(self) -> UserConnectionRepository:
        """Create UserConnectionRepository instance."""
        return UserConnectionRepository(UserConnection)

    def test_create(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test creating a new user connection."""
        # Arrange
        user = create_user(db)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=30)

        connection_data = UserConnectionCreate(
            id=uuid4(),
            user_id=user.id,
            provider="garmin",
            provider_user_id="garmin_12345",
            provider_username="athlete123",
            access_token="access_token_xyz",
            refresh_token="refresh_token_abc",
            token_expires_at=expires_at,
            scope="read_all",
            status=ConnectionStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )

        # Act
        result = connection_repo.create(db, connection_data)

        # Assert
        assert result.id == connection_data.id
        assert result.user_id == user.id
        assert result.provider == "garmin"
        assert result.provider_user_id == "garmin_12345"
        assert result.access_token == "access_token_xyz"
        assert result.status == ConnectionStatus.ACTIVE

        # Verify in database
        db.expire_all()
        db_connection = connection_repo.get(db, connection_data.id)
        assert db_connection is not None
        assert db_connection.provider == "garmin"

    def test_get(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test retrieving a connection by ID."""
        # Arrange
        connection = create_user_connection(db, provider="polar", status=ConnectionStatus.ACTIVE)

        # Act
        result = connection_repo.get(db, connection.id)

        # Assert
        assert result is not None
        assert result.id == connection.id
        assert result.provider == "polar"

    def test_get_by_user_and_provider(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test retrieving a connection by user and provider."""
        # Arrange
        user = create_user(db)
        connection = create_user_connection(db, user=user, provider="garmin", status=ConnectionStatus.ACTIVE)
        create_user_connection(db, user=user, provider="polar", status=ConnectionStatus.ACTIVE)

        # Act
        result = connection_repo.get_by_user_and_provider(db, user.id, "garmin")

        # Assert
        assert result is not None
        assert result.id == connection.id
        assert result.provider == "garmin"

    def test_get_by_user_and_provider_not_found(
        self,
        db: Session,
        connection_repo: UserConnectionRepository,
    ) -> None:
        """Test get_by_user_and_provider returns None when not found."""
        # Arrange
        user = create_user(db)
        create_user_connection(db, user=user, provider="garmin")

        # Act
        result = connection_repo.get_by_user_and_provider(db, user.id, "polar")

        # Assert
        assert result is None

    def test_get_active_connection(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test retrieving an active connection for a user and provider."""
        # Arrange
        user = create_user(db)
        active_conn = create_user_connection(db, user=user, provider="garmin", status=ConnectionStatus.ACTIVE)
        create_user_connection(db, user=user, provider="polar", status=ConnectionStatus.REVOKED)

        # Act
        result = connection_repo.get_active_connection(db, user.id, "garmin")

        # Assert
        assert result is not None
        assert result.id == active_conn.id
        assert result.status == ConnectionStatus.ACTIVE

    def test_get_active_connection_only_returns_active(
        self,
        db: Session,
        connection_repo: UserConnectionRepository,
    ) -> None:
        """Test that get_active_connection ignores revoked connections."""
        # Arrange
        user = create_user(db)
        create_user_connection(db, user=user, provider="polar", status=ConnectionStatus.REVOKED)
        # Create another user to avoid unique constraint violation
        user2 = create_user(db)
        create_user_connection(db, user=user2, provider="polar", status=ConnectionStatus.EXPIRED)

        # Act
        result = connection_repo.get_active_connection(db, user.id, "polar")

        # Assert
        assert result is None

    def test_get_by_provider_user_id(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test retrieving a connection by provider and provider's user ID."""
        # Arrange
        connection = create_user_connection(
            db,
            provider="garmin",
            provider_user_id="garmin_athlete_789",
            status=ConnectionStatus.ACTIVE,
        )

        # Act
        result = connection_repo.get_by_provider_user_id(db, "garmin", "garmin_athlete_789")

        # Assert
        assert result is not None
        assert result.id == connection.id
        assert result.provider_user_id == "garmin_athlete_789"

    def test_get_by_provider_user_id_only_returns_active(
        self,
        db: Session,
        connection_repo: UserConnectionRepository,
    ) -> None:
        """Test that get_by_provider_user_id only returns active connections."""
        # Arrange
        create_user_connection(
            db,
            provider="garmin",
            provider_user_id="garmin_123",
            status=ConnectionStatus.REVOKED,
        )

        # Act
        result = connection_repo.get_by_provider_user_id(db, "garmin", "garmin_123")

        # Assert
        assert result is None

    def test_get_by_user_id(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test retrieving all connections for a specific user."""
        # Arrange
        user = create_user(db)
        conn1 = create_user_connection(db, user=user, provider="garmin")
        conn2 = create_user_connection(db, user=user, provider="polar")
        create_user_connection(db)  # Different user

        # Act
        results = connection_repo.get_by_user_id(db, user.id)

        # Assert
        assert len(results) >= 2
        connection_ids = {c.id for c in results}
        assert conn1.id in connection_ids
        assert conn2.id in connection_ids

    def test_get_by_user_id_ordered_by_created_desc(
        self,
        db: Session,
        connection_repo: UserConnectionRepository,
    ) -> None:
        """Test that get_by_user_id returns connections ordered by creation date descending."""
        # Arrange
        user = create_user(db)
        now = datetime.now(timezone.utc)

        conn1 = create_user_connection(db, user=user, provider="garmin", created_at=now - timedelta(days=2))
        conn2 = create_user_connection(db, user=user, provider="polar", created_at=now - timedelta(days=1))
        conn3 = create_user_connection(db, user=user, provider="suunto", created_at=now)

        # Act
        results = connection_repo.get_by_user_id(db, user.id)

        # Assert
        assert len(results) >= 3
        # Most recent first
        assert results[0].id == conn3.id
        assert results[1].id == conn2.id
        assert results[2].id == conn1.id

    def test_get_expiring_tokens(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test retrieving connections with tokens expiring soon."""
        # Arrange
        now = datetime.now(timezone.utc)
        expires_soon = now + timedelta(minutes=3)
        expires_later = now + timedelta(hours=2)
        expired = now - timedelta(minutes=1)

        conn_expiring = create_user_connection(
            db,
            provider="garmin",
            status=ConnectionStatus.ACTIVE,
            token_expires_at=expires_soon,
        )
        create_user_connection(
            db,
            provider="polar",
            status=ConnectionStatus.ACTIVE,
            token_expires_at=expires_later,
        )
        create_user_connection(
            db,
            provider="suunto",
            status=ConnectionStatus.ACTIVE,
            token_expires_at=expired,
        )

        # Act - Get tokens expiring in next 5 minutes
        results = connection_repo.get_expiring_tokens(db, minutes_threshold=5)

        # Assert
        expiring_ids = {c.id for c in results}
        assert conn_expiring.id in expiring_ids

    def test_get_expiring_tokens_ignores_revoked(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test that get_expiring_tokens only returns active connections."""
        # Arrange
        now = datetime.now(timezone.utc)
        expires_soon = now + timedelta(minutes=3)

        create_user_connection(
            db,
            provider="garmin",
            status=ConnectionStatus.REVOKED,
            token_expires_at=expires_soon,
        )

        # Act
        results = connection_repo.get_expiring_tokens(db, minutes_threshold=5)

        # Assert
        # Should not include revoked connection
        revoked_in_results = any(c.status == ConnectionStatus.REVOKED for c in results)
        assert not revoked_in_results

    def test_mark_as_revoked(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test marking a connection as revoked."""
        # Arrange
        connection = create_user_connection(db, provider="garmin", status=ConnectionStatus.ACTIVE)
        original_updated_at = connection.updated_at

        # Wait to ensure timestamp difference
        import time

        time.sleep(0.01)

        # Act
        result = connection_repo.mark_as_revoked(db, connection)

        # Assert
        assert result.status == ConnectionStatus.REVOKED
        assert result.updated_at > original_updated_at

        # Verify in database
        db.expire_all()
        db_connection = connection_repo.get(db, connection.id)
        assert db_connection.status == ConnectionStatus.REVOKED

    def test_update_tokens(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test updating connection tokens."""
        # Arrange
        connection = create_user_connection(
            db,
            access_token="old_access",
            refresh_token="old_refresh",
        )
        original_updated_at = connection.updated_at

        # Wait to ensure timestamp difference
        import time

        time.sleep(0.01)

        # Act
        result = connection_repo.update_tokens(
            db,
            connection,
            access_token="new_access",
            refresh_token="new_refresh",
            expires_in=3600,
        )

        # Assert
        assert result.access_token == "new_access"
        assert result.refresh_token == "new_refresh"
        assert result.updated_at > original_updated_at
        # Token should expire in approximately 1 hour
        expected_expiry = datetime.now(timezone.utc) + timedelta(seconds=3600)
        assert abs((result.token_expires_at - expected_expiry).total_seconds()) < 5

    def test_update_tokens_with_none_refresh_token(
        self,
        db: Session,
        connection_repo: UserConnectionRepository,
    ) -> None:
        """Test updating tokens without changing refresh token."""
        # Arrange
        connection = create_user_connection(
            db,
            access_token="old_access",
            refresh_token="original_refresh",
        )

        # Act
        result = connection_repo.update_tokens(
            db,
            connection,
            access_token="new_access",
            refresh_token=None,
            expires_in=3600,
        )

        # Assert
        assert result.access_token == "new_access"
        assert result.refresh_token == "original_refresh"  # Unchanged

    def test_get_active_count(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test counting active connections."""
        # Arrange
        initial_count = connection_repo.get_active_count(db)

        create_user_connection(db, status=ConnectionStatus.ACTIVE)
        create_user_connection(db, status=ConnectionStatus.ACTIVE)
        create_user_connection(db, status=ConnectionStatus.REVOKED)

        # Act
        result = connection_repo.get_active_count(db)

        # Assert
        assert result == initial_count + 2

    def test_get_active_count_in_range(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test counting active connections created within a date range."""
        # Arrange
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        create_user_connection(db, status=ConnectionStatus.ACTIVE, created_at=two_days_ago)
        create_user_connection(db, status=ConnectionStatus.ACTIVE, created_at=yesterday)
        create_user_connection(db, status=ConnectionStatus.ACTIVE, created_at=yesterday)
        create_user_connection(db, status=ConnectionStatus.ACTIVE, created_at=now)
        create_user_connection(db, status=ConnectionStatus.REVOKED, created_at=yesterday)  # Should not count

        # Act - Count active connections created yesterday
        result = connection_repo.get_active_count_in_range(db, yesterday, now)

        # Assert
        assert result == 2  # Two active connections created yesterday

    def test_get_all_active_by_user(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test getting all active connections for a specific user."""
        # Arrange
        user = create_user(db)
        active_conn1 = create_user_connection(db, user=user, provider="garmin", status=ConnectionStatus.ACTIVE)
        active_conn2 = create_user_connection(db, user=user, provider="polar", status=ConnectionStatus.ACTIVE)
        create_user_connection(db, user=user, provider="suunto", status=ConnectionStatus.REVOKED)

        # Act
        results = connection_repo.get_all_active_by_user(db, user.id)

        # Assert
        assert len(results) == 2
        connection_ids = {c.id for c in results}
        assert active_conn1.id in connection_ids
        assert active_conn2.id in connection_ids
        # All should be active
        for conn in results:
            assert conn.status == ConnectionStatus.ACTIVE

    def test_get_all_active_users(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test getting all unique user IDs with active connections."""
        # Arrange
        user1 = create_user(db)
        user2 = create_user(db)
        user3 = create_user(db)

        create_user_connection(db, user=user1, status=ConnectionStatus.ACTIVE)
        create_user_connection(
            db,
            user=user1,
            provider="polar",
            status=ConnectionStatus.ACTIVE,
        )  # Same user, different provider
        create_user_connection(db, user=user2, status=ConnectionStatus.ACTIVE)
        create_user_connection(db, user=user3, status=ConnectionStatus.REVOKED)  # Should not be included

        # Act
        results = connection_repo.get_all_active_users(db)

        # Assert
        assert user1.id in results
        assert user2.id in results
        assert user3.id not in results
        # Check that user1 appears only once despite having 2 connections
        assert results.count(user1.id) == 1

    def test_update(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test updating a connection using the base update method."""
        # Arrange
        connection = create_user_connection(db, provider_username="old_username")
        update_data = UserConnectionUpdate(
            provider_username="new_username",
            status=ConnectionStatus.REVOKED,
        )

        # Act
        result = connection_repo.update(db, connection, update_data)

        # Assert
        assert result.provider_username == "new_username"
        assert result.status == ConnectionStatus.REVOKED

    def test_delete(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test deleting a connection."""
        # Arrange
        connection = create_user_connection(db)
        connection_id = connection.id

        # Act
        connection_repo.delete(db, connection)

        # Assert
        db.expire_all()
        deleted_connection = connection_repo.get(db, connection_id)
        assert deleted_connection is None

    def test_multiple_connections_same_user_different_providers(
        self,
        db: Session,
        connection_repo: UserConnectionRepository,
    ) -> None:
        """Test that a user can have connections to multiple providers."""
        # Arrange
        user = create_user(db)
        conn_garmin = create_user_connection(db, user=user, provider="garmin", status=ConnectionStatus.ACTIVE)
        conn_polar = create_user_connection(db, user=user, provider="polar", status=ConnectionStatus.ACTIVE)
        conn_suunto = create_user_connection(db, user=user, provider="suunto", status=ConnectionStatus.ACTIVE)

        # Act
        garmin_conn = connection_repo.get_active_connection(db, user.id, "garmin")
        polar_conn = connection_repo.get_active_connection(db, user.id, "polar")
        suunto_conn = connection_repo.get_active_connection(db, user.id, "suunto")

        # Assert
        assert garmin_conn.id == conn_garmin.id
        assert polar_conn.id == conn_polar.id
        assert suunto_conn.id == conn_suunto.id

    def test_connection_status_transitions(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test transitioning connection through different statuses."""
        # Arrange
        connection = create_user_connection(db, status=ConnectionStatus.ACTIVE)

        # Act - Mark as revoked
        connection_repo.mark_as_revoked(db, connection)
        db.expire_all()
        revoked_conn = connection_repo.get(db, connection.id)

        # Assert
        assert revoked_conn.status == ConnectionStatus.REVOKED

        # Update to expired
        update_data = UserConnectionUpdate(status=ConnectionStatus.EXPIRED)
        connection_repo.update(db, revoked_conn, update_data)
        db.expire_all()
        expired_conn = connection_repo.get(db, connection.id)

        assert expired_conn.status == ConnectionStatus.EXPIRED

    def test_last_synced_at_update(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test updating last_synced_at timestamp."""
        # Arrange
        connection = create_user_connection(db, last_synced_at=None)
        assert connection.last_synced_at is None

        # Act
        now = datetime.now(timezone.utc)
        update_data = UserConnectionUpdate(last_synced_at=now)
        result = connection_repo.update(db, connection, update_data)

        # Assert
        assert result.last_synced_at is not None
        assert abs((result.last_synced_at - now).total_seconds()) < 1

    def test_get_all_with_filters(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test filtering connections using get_all."""
        # Arrange
        user = create_user(db)
        conn1 = create_user_connection(db, user=user, provider="garmin")
        create_user_connection(db, user=user, provider="polar")

        # Act
        results = connection_repo.get_all(
            db,
            filters={"provider": "garmin"},
            offset=0,
            limit=10,
            sort_by=None,
        )

        # Assert
        garmin_conns = [c for c in results if c.provider == "garmin"]
        assert len(garmin_conns) >= 1
        assert conn1.id in [c.id for c in garmin_conns]

    def test_get_expiring_tokens_custom_threshold(self, db: Session, connection_repo: UserConnectionRepository) -> None:
        """Test get_expiring_tokens with custom time threshold."""
        # Arrange
        now = datetime.now(timezone.utc)
        expires_in_2_min = now + timedelta(minutes=2)
        expires_in_8_min = now + timedelta(minutes=8)

        conn1 = create_user_connection(
            db,
            status=ConnectionStatus.ACTIVE,
            token_expires_at=expires_in_2_min,
        )
        create_user_connection(
            db,
            status=ConnectionStatus.ACTIVE,
            token_expires_at=expires_in_8_min,
        )

        # Act - Get tokens expiring in next 3 minutes
        results = connection_repo.get_expiring_tokens(db, minutes_threshold=3)

        # Assert
        expiring_ids = {c.id for c in results}
        assert conn1.id in expiring_ids
        # 8-minute expiry should not be included
        assert all(c.token_expires_at <= now + timedelta(minutes=3) for c in results if c.id == conn1.id)
