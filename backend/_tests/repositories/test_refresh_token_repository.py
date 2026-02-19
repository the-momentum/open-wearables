"""
Unit tests for refresh token repository.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import RefreshToken
from app.repositories.refresh_token_repository import refresh_token_repository
from app.schemas.token_type import TokenType
from _tests.factories import DeveloperFactory, UserFactory


class TestRefreshTokenRepository:
    """Tests for RefreshTokenRepository."""

    def test_create_token(self, db: Session) -> None:
        """Creating a token should persist it to the database."""
        # Arrange
        user = UserFactory()
        token = RefreshToken(
            id="rt-test123456789012345678901234",
            token_type=TokenType.SDK,
            user_id=user.id,
            app_id="test_app",
            developer_id=None,
            created_at=datetime.now(timezone.utc),
            last_used_at=None,
            revoked_at=None,
        )

        # Act
        created = refresh_token_repository.create(db, token)

        # Assert
        assert created.id == "rt-test123456789012345678901234"
        assert created.token_type == TokenType.SDK
        assert created.user_id == user.id

    def test_get_valid_token(self, db: Session) -> None:
        """get_valid_token should return token if not revoked."""
        # Arrange
        user = UserFactory()
        token = RefreshToken(
            id="rt-validtoken123456789012345678",
            token_type=TokenType.SDK,
            user_id=user.id,
            app_id="test_app",
            developer_id=None,
            created_at=datetime.now(timezone.utc),
            last_used_at=None,
            revoked_at=None,
        )
        db.add(token)
        db.commit()

        # Act
        result = refresh_token_repository.get_valid_token(db, token.id)

        # Assert
        assert result is not None
        assert result.id == token.id

    def test_get_valid_token_returns_none_for_revoked(self, db: Session) -> None:
        """get_valid_token should return None if token is revoked."""
        # Arrange
        user = UserFactory()
        token = RefreshToken(
            id="rt-revokedtoken12345678901234567",
            token_type=TokenType.SDK,
            user_id=user.id,
            app_id="test_app",
            developer_id=None,
            created_at=datetime.now(timezone.utc),
            last_used_at=None,
            revoked_at=datetime.now(timezone.utc),
        )
        db.add(token)
        db.commit()

        # Act
        result = refresh_token_repository.get_valid_token(db, token.id)

        # Assert
        assert result is None

    def test_get_by_user_id(self, db: Session) -> None:
        """get_by_user_id should return all non-revoked tokens for a user."""
        # Arrange
        user = UserFactory()
        token1 = RefreshToken(
            id="rt-user1token1234567890123456789",
            token_type=TokenType.SDK,
            user_id=user.id,
            app_id="app1",
            developer_id=None,
            created_at=datetime.now(timezone.utc),
            last_used_at=None,
            revoked_at=None,
        )
        token2 = RefreshToken(
            id="rt-user1token2345678901234567890",
            token_type=TokenType.SDK,
            user_id=user.id,
            app_id="app2",
            developer_id=None,
            created_at=datetime.now(timezone.utc),
            last_used_at=None,
            revoked_at=None,
        )
        db.add(token1)
        db.add(token2)
        db.commit()

        # Act
        result = refresh_token_repository.get_by_user_id(db, user.id)

        # Assert
        assert len(result) == 2

    def test_get_by_developer_id(self, db: Session) -> None:
        """get_by_developer_id should return all non-revoked tokens for a developer."""
        # Arrange
        developer = DeveloperFactory()
        token1 = RefreshToken(
            id="rt-dev1token12345678901234567890",
            token_type=TokenType.DEVELOPER,
            user_id=None,
            app_id=None,
            developer_id=developer.id,
            created_at=datetime.now(timezone.utc),
            last_used_at=None,
            revoked_at=None,
        )
        db.add(token1)
        db.commit()

        # Act
        result = refresh_token_repository.get_by_developer_id(db, developer.id)

        # Assert
        assert len(result) == 1
        assert result[0].developer_id == developer.id

    def test_revoke_token(self, db: Session) -> None:
        """revoke_token should set revoked_at timestamp."""
        # Arrange
        user = UserFactory()
        token = RefreshToken(
            id="rt-torevoke123456789012345678901",
            token_type=TokenType.SDK,
            user_id=user.id,
            app_id="test_app",
            developer_id=None,
            created_at=datetime.now(timezone.utc),
            last_used_at=None,
            revoked_at=None,
        )
        db.add(token)
        db.commit()

        # Act
        refresh_token_repository.revoke_token(db, token)

        # Assert
        db.refresh(token)
        assert token.revoked_at is not None

    def test_revoke_all_for_user(self, db: Session) -> None:
        """revoke_all_for_user should revoke all tokens for a user."""
        # Arrange
        user = UserFactory()
        token1 = RefreshToken(
            id="rt-revokeall123456789012345678901",
            token_type=TokenType.SDK,
            user_id=user.id,
            app_id="app1",
            developer_id=None,
            created_at=datetime.now(timezone.utc),
            last_used_at=None,
            revoked_at=None,
        )
        token2 = RefreshToken(
            id="rt-revokeall234567890123456789012",
            token_type=TokenType.SDK,
            user_id=user.id,
            app_id="app2",
            developer_id=None,
            created_at=datetime.now(timezone.utc),
            last_used_at=None,
            revoked_at=None,
        )
        db.add(token1)
        db.add(token2)
        db.commit()

        # Act
        count = refresh_token_repository.revoke_all_for_user(db, user.id)

        # Assert
        assert count == 2
        db.refresh(token1)
        db.refresh(token2)
        assert token1.revoked_at is not None
        assert token2.revoked_at is not None

    def test_revoke_all_for_developer(self, db: Session) -> None:
        """revoke_all_for_developer should revoke all tokens for a developer."""
        # Arrange
        developer = DeveloperFactory()
        token = RefreshToken(
            id="rt-revokedev123456789012345678901",
            token_type=TokenType.DEVELOPER,
            user_id=None,
            app_id=None,
            developer_id=developer.id,
            created_at=datetime.now(timezone.utc),
            last_used_at=None,
            revoked_at=None,
        )
        db.add(token)
        db.commit()

        # Act
        count = refresh_token_repository.revoke_all_for_developer(db, developer.id)

        # Assert
        assert count == 1
        db.refresh(token)
        assert token.revoked_at is not None

    def test_update_last_used(self, db: Session) -> None:
        """update_last_used should set last_used_at timestamp."""
        # Arrange
        user = UserFactory()
        token = RefreshToken(
            id="rt-updateused12345678901234567890",
            token_type=TokenType.SDK,
            user_id=user.id,
            app_id="test_app",
            developer_id=None,
            created_at=datetime.now(timezone.utc),
            last_used_at=None,
            revoked_at=None,
        )
        db.add(token)
        db.commit()
        assert token.last_used_at is None

        # Act
        refresh_token_repository.update_last_used(db, token)

        # Assert
        db.refresh(token)
        assert token.last_used_at is not None
