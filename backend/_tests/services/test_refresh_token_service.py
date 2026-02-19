"""
Unit tests for refresh token service.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import RefreshToken
from app.schemas.token_type import TokenType
from app.services.refresh_token_service import refresh_token_service
from _tests.factories import DeveloperFactory, UserFactory


class TestCreateSDKRefreshToken:
    """Tests for create_sdk_refresh_token."""

    def test_create_sdk_refresh_token_format(self, db: Session) -> None:
        """SDK refresh token should have rt- prefix and be 35 characters total."""
        # Arrange
        user = UserFactory()
        app_id = "test_app_123"

        # Act
        token = refresh_token_service.create_sdk_refresh_token(db, user.id, app_id)

        # Assert
        assert token.startswith("rt-")
        assert len(token) == 35  # "rt-" (3) + 32 hex chars

    def test_create_sdk_refresh_token_stored_in_db(self, db: Session) -> None:
        """SDK refresh token should be stored in database with correct metadata."""
        # Arrange
        user = UserFactory()
        app_id = "test_app_123"

        # Act
        token = refresh_token_service.create_sdk_refresh_token(db, user.id, app_id)

        # Assert
        db_token = db.query(RefreshToken).filter(RefreshToken.id == token).first()
        assert db_token is not None
        assert db_token.token_type == TokenType.SDK
        assert db_token.user_id == user.id
        assert db_token.app_id == app_id
        assert db_token.developer_id is None
        assert db_token.revoked_at is None


class TestCreateDeveloperRefreshToken:
    """Tests for create_developer_refresh_token."""

    def test_create_developer_refresh_token_format(self, db: Session) -> None:
        """Developer refresh token should have rt- prefix and be 35 characters total."""
        # Arrange
        developer = DeveloperFactory()

        # Act
        token = refresh_token_service.create_developer_refresh_token(db, developer.id)

        # Assert
        assert token.startswith("rt-")
        assert len(token) == 35  # "rt-" (3) + 32 hex chars

    def test_create_developer_refresh_token_stored_in_db(self, db: Session) -> None:
        """Developer refresh token should be stored in database with correct metadata."""
        # Arrange
        developer = DeveloperFactory()

        # Act
        token = refresh_token_service.create_developer_refresh_token(db, developer.id)

        # Assert
        db_token = db.query(RefreshToken).filter(RefreshToken.id == token).first()
        assert db_token is not None
        assert db_token.token_type == TokenType.DEVELOPER
        assert db_token.developer_id == developer.id
        assert db_token.user_id is None
        assert db_token.app_id is None
        assert db_token.revoked_at is None


class TestRefreshToken:
    """Tests for refresh_token method."""

    def test_refresh_sdk_token_success(self, db: Session) -> None:
        """Refreshing SDK token should return new access token and rotated refresh token."""
        # Arrange
        user = UserFactory()
        app_id = "test_app_123"
        refresh_token = refresh_token_service.create_sdk_refresh_token(db, user.id, app_id)

        # Act
        result = refresh_token_service.refresh_token(db, refresh_token)

        # Assert
        assert result.access_token is not None
        assert result.token_type == "bearer"
        # Refresh token should be rotated
        assert result.refresh_token != refresh_token
        assert result.refresh_token.startswith("rt-")

    def test_refresh_developer_token_success(self, db: Session) -> None:
        """Refreshing developer token should return new access token and rotated refresh token."""
        # Arrange
        developer = DeveloperFactory()
        refresh_token = refresh_token_service.create_developer_refresh_token(db, developer.id)

        # Act
        result = refresh_token_service.refresh_token(db, refresh_token)

        # Assert
        assert result.access_token is not None
        assert result.token_type == "bearer"
        # Refresh token should be rotated
        assert result.refresh_token != refresh_token
        assert result.refresh_token.startswith("rt-")

    def test_refresh_invalid_token_raises_401(self, db: Session) -> None:
        """Refreshing invalid token should raise 401."""
        # Arrange
        invalid_token = "rt-invalidtoken12345678901234567890"

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            refresh_token_service.refresh_token(db, invalid_token)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid or revoked refresh token"

    def test_refresh_revoked_token_raises_401(self, db: Session) -> None:
        """Refreshing revoked token should raise 401."""
        # Arrange
        user = UserFactory()
        refresh_token = refresh_token_service.create_sdk_refresh_token(db, user.id, "test_app")
        refresh_token_service.revoke_token(db, refresh_token)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            refresh_token_service.refresh_token(db, refresh_token)

        assert exc_info.value.status_code == 401

    def test_refresh_revokes_old_token(self, db: Session) -> None:
        """Refreshing token should revoke the old token (rotation)."""
        # Arrange
        user = UserFactory()
        old_refresh_token = refresh_token_service.create_sdk_refresh_token(db, user.id, "test_app")

        # Verify not revoked initially
        db_token = db.query(RefreshToken).filter(RefreshToken.id == old_refresh_token).first()
        assert db_token is not None
        assert db_token.revoked_at is None

        # Act
        result = refresh_token_service.refresh_token(db, old_refresh_token)

        # Assert - old token is revoked
        db.refresh(db_token)
        assert db_token.revoked_at is not None

        # Assert - new token exists and is not revoked
        new_db_token = db.query(RefreshToken).filter(RefreshToken.id == result.refresh_token).first()
        assert new_db_token is not None
        assert new_db_token.revoked_at is None


class TestRevokeToken:
    """Tests for revoke_token method."""

    def test_revoke_token_success(self, db: Session) -> None:
        """Revoking token should set revoked_at timestamp."""
        # Arrange
        user = UserFactory()
        refresh_token = refresh_token_service.create_sdk_refresh_token(db, user.id, "test_app")

        # Act
        result = refresh_token_service.revoke_token(db, refresh_token)

        # Assert
        assert result is True
        db_token = db.query(RefreshToken).filter(RefreshToken.id == refresh_token).first()
        assert db_token is not None
        assert db_token.revoked_at is not None

    def test_revoke_nonexistent_token_raises_404(self, db: Session) -> None:
        """Revoking non-existent token should raise 404."""
        # Arrange
        invalid_token = "rt-nonexistent123456789012345678"

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            refresh_token_service.revoke_token(db, invalid_token)

        assert exc_info.value.status_code == 404

    def test_revoke_already_revoked_token_raises_404(self, db: Session) -> None:
        """Revoking already revoked token should raise 404."""
        # Arrange
        user = UserFactory()
        refresh_token = refresh_token_service.create_sdk_refresh_token(db, user.id, "test_app")
        refresh_token_service.revoke_token(db, refresh_token)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            refresh_token_service.revoke_token(db, refresh_token)

        assert exc_info.value.status_code == 404
