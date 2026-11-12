"""
Unit tests for refresh token service.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.config import settings

from app.models import RefreshToken
from app.schemas.auth import SDKTokenOrigin, TokenType
from app.services.refresh_token_service import refresh_token_service
from app.utils.exceptions import AuthenticationError, NotFoundError
from tests.factories import ApplicationFactory, DeveloperFactory, UserFactory


class TestCreateSDKRefreshToken:
    """Tests for create_sdk_refresh_token."""

    def test_create_sdk_refresh_token_format(self, db: Session) -> None:
        """SDK refresh token should have rt- prefix and be 35 characters total."""
        # Arrange
        user = UserFactory()

        # Act
        token = refresh_token_service.create_sdk_refresh_token(db, user.id, SDKTokenOrigin.ADMIN)

        # Assert
        assert token.startswith("rt-")
        assert len(token) == 35  # "rt-" (3) + 32 hex chars

    def test_create_sdk_refresh_token_stored_in_db(self, db: Session) -> None:
        """SDK refresh token should be stored in database with correct metadata."""
        # Arrange
        user = UserFactory()
        application = ApplicationFactory(developer=DeveloperFactory())

        # Act
        token = refresh_token_service.create_sdk_refresh_token(
            db, user.id, SDKTokenOrigin.APPLICATION, application_id=application.id
        )

        # Assert
        db_token = db.query(RefreshToken).filter(RefreshToken.id == token).first()
        assert db_token is not None
        assert db_token.token_type == TokenType.SDK
        assert db_token.user_id == user.id
        assert db_token.origin == SDKTokenOrigin.APPLICATION
        assert db_token.application_id == application.id
        assert db_token.issued_by_developer_id is None
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
        assert db_token.origin is None
        assert db_token.application_id is None
        assert db_token.revoked_at is None


class TestRefreshToken:
    """Tests for refresh_token method."""

    def test_refresh_sdk_token_success(self, db: Session) -> None:
        """Refreshing SDK token should return new access token and rotated refresh token."""
        # Arrange
        user = UserFactory()
        refresh_token = refresh_token_service.create_sdk_refresh_token(db, user.id, SDKTokenOrigin.ADMIN)

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
        with pytest.raises(AuthenticationError) as exc_info:
            refresh_token_service.refresh_token(db, invalid_token)

        assert exc_info.value.status_code == 401

    def test_refresh_expired_developer_token_raises_401(self, db: Session) -> None:
        """Refreshing an expired developer token (older than expire days) should raise 401."""
        # Arrange
        developer = DeveloperFactory()
        expired_token = RefreshToken(
            id="rt-expireddevtest12345678901234",
            token_type=TokenType.DEVELOPER,
            user_id=None,
            origin=None,
            developer_id=developer.id,
            created_at=datetime.now(timezone.utc) - timedelta(days=settings.developer_refresh_token_expire_days + 1),
            last_used_at=None,
            revoked_at=None,
        )
        db.add(expired_token)
        db.commit()

        # Act & Assert
        with pytest.raises(AuthenticationError) as exc_info:
            refresh_token_service.refresh_token(db, expired_token.id)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid or revoked refresh token"

    def test_refresh_developer_token_just_within_expiry_succeeds(self, db: Session) -> None:
        """Refreshing a developer token just within its lifetime should succeed."""
        # Arrange
        developer = DeveloperFactory()
        valid_token = RefreshToken(
            id="rt-validdevtest1234567890123456",
            token_type=TokenType.DEVELOPER,
            user_id=None,
            origin=None,
            developer_id=developer.id,
            created_at=datetime.now(timezone.utc) - timedelta(days=settings.developer_refresh_token_expire_days - 1),
            last_used_at=None,
            revoked_at=None,
        )
        db.add(valid_token)
        db.commit()

        # Act
        result = refresh_token_service.refresh_token(db, valid_token.id)

        # Assert
        assert result.access_token is not None
        assert result.refresh_token.startswith("rt-")

    def test_refresh_old_sdk_token_succeeds(self, db: Session) -> None:
        """Refreshing an old SDK token should succeed because developer lifetime does not apply to SDK."""
        # Arrange
        user = UserFactory()
        old_sdk_token = RefreshToken(
            id="rt-oldsdktest123456789012345678",
            token_type=TokenType.SDK,
            user_id=user.id,
            origin=SDKTokenOrigin.ADMIN,
            developer_id=None,
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
            last_used_at=None,
            revoked_at=None,
        )
        db.add(old_sdk_token)
        db.commit()

        # Act
        result = refresh_token_service.refresh_token(db, old_sdk_token.id)

        # Assert
        assert result.access_token is not None
        assert result.refresh_token.startswith("rt-")

    def test_refresh_developer_token_respects_custom_expiry_setting(self, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        """Refreshing a developer token should respect custom developer_refresh_token_expire_days setting."""
        # Arrange
        monkeypatch.setattr(settings, "developer_refresh_token_expire_days", 7)
        developer = DeveloperFactory()
        ten_day_old_token = RefreshToken(
            id="rt-customexpiretest123456789012",
            token_type=TokenType.DEVELOPER,
            user_id=None,
            origin=None,
            developer_id=developer.id,
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
            last_used_at=None,
            revoked_at=None,
        )
        db.add(ten_day_old_token)
        db.commit()

        # Act & Assert
        with pytest.raises(AuthenticationError) as exc_info:
            refresh_token_service.refresh_token(db, ten_day_old_token.id)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid or revoked refresh token"

    def test_refresh_revoked_token_raises_401(self, db: Session) -> None:
        """Refreshing revoked token should raise 401."""
        # Arrange
        user = UserFactory()
        refresh_token = refresh_token_service.create_sdk_refresh_token(db, user.id, SDKTokenOrigin.ADMIN)
        refresh_token_service.revoke_token(db, refresh_token)

        # Act & Assert
        with pytest.raises(AuthenticationError) as exc_info:
            refresh_token_service.refresh_token(db, refresh_token)

        assert exc_info.value.status_code == 401

    def test_refresh_revokes_old_token(self, db: Session) -> None:
        """Refreshing token should revoke the old token (rotation)."""
        # Arrange
        user = UserFactory()
        old_refresh_token = refresh_token_service.create_sdk_refresh_token(db, user.id, SDKTokenOrigin.ADMIN)

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

    @pytest.mark.parametrize("token_type", [TokenType.SDK, TokenType.DEVELOPER])
    def test_refresh_keeps_old_token_usable_when_issuing_tokens_fails(self, db: Session, token_type: TokenType) -> None:
        """A refresh that fails to issue the new pair must not burn the old token."""
        # Arrange
        if token_type == TokenType.SDK:
            old_refresh_token = refresh_token_service.create_sdk_refresh_token(
                db, UserFactory().id, SDKTokenOrigin.ADMIN
            )
            failing_step = "create_sdk_refresh_token"
        else:
            old_refresh_token = refresh_token_service.create_developer_refresh_token(db, DeveloperFactory().id)
            failing_step = "create_developer_refresh_token"

        # Act
        with (
            patch.object(refresh_token_service, failing_step, side_effect=RuntimeError("db down")),
            pytest.raises(RuntimeError),
        ):
            refresh_token_service.refresh_token(db, old_refresh_token)
        db.rollback()  # what the request's session dependency does on an error

        # Assert
        old_row = db.get(RefreshToken, old_refresh_token)
        assert old_row is not None
        assert old_row.revoked_at is None
        result = refresh_token_service.refresh_token(db, old_refresh_token)
        db.refresh(old_row)
        assert old_row.revoked_at is not None
        assert db.get(RefreshToken, result.refresh_token) is not None


class TestRevokeToken:
    """Tests for revoke_token method."""

    def test_revoke_token_success(self, db: Session) -> None:
        """Revoking token should set revoked_at timestamp."""
        # Arrange
        user = UserFactory()
        refresh_token = refresh_token_service.create_sdk_refresh_token(db, user.id, SDKTokenOrigin.ADMIN)

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
        with pytest.raises(NotFoundError) as exc_info:
            refresh_token_service.revoke_token(db, invalid_token)

        assert exc_info.value.status_code == 404

    def test_revoke_already_revoked_token_raises_404(self, db: Session) -> None:
        """Revoking already revoked token should raise 404."""
        # Arrange
        user = UserFactory()
        refresh_token = refresh_token_service.create_sdk_refresh_token(db, user.id, SDKTokenOrigin.ADMIN)
        refresh_token_service.revoke_token(db, refresh_token)

        # Act & Assert
        with pytest.raises(NotFoundError) as exc_info:
            refresh_token_service.revoke_token(db, refresh_token)

        assert exc_info.value.status_code == 404
