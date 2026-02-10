"""Unit tests for user invitation code service."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from jose import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user_invitation_code import UserInvitationCode
from app.services.user_invitation_code_service import (
    CODE_ALPHABET,
    CODE_LENGTH,
    user_invitation_code_service,
)
from tests.factories import DeveloperFactory, UserFactory


class TestGenerate:
    """Tests for generate method."""

    def test_generate_returns_valid_code(self, db: Session) -> None:
        # Arrange
        developer = DeveloperFactory()
        user = UserFactory()

        # Act
        result = user_invitation_code_service.generate(db, user.id, developer.id)

        # Assert
        assert len(result.code) == CODE_LENGTH
        assert all(c in CODE_ALPHABET for c in result.code)
        assert result.user_id == user.id

    def test_generate_sets_expiry(self, db: Session) -> None:
        # Arrange
        developer = DeveloperFactory()
        user = UserFactory()

        # Act
        result = user_invitation_code_service.generate(db, user.id, developer.id)

        # Assert
        expected_expiry = datetime.now(timezone.utc) + timedelta(days=settings.user_invitation_code_expire_days)
        assert abs((result.expires_at - expected_expiry).total_seconds()) < 5

    def test_generate_stores_in_db(self, db: Session) -> None:
        # Arrange
        developer = DeveloperFactory()
        user = UserFactory()

        # Act
        result = user_invitation_code_service.generate(db, user.id, developer.id)

        # Assert
        db_code = db.query(UserInvitationCode).filter(UserInvitationCode.id == result.id).first()
        assert db_code is not None
        assert db_code.code == result.code
        assert db_code.created_by_id == developer.id
        assert db_code.redeemed_at is None
        assert db_code.revoked_at is None

    def test_generate_nonexistent_user_raises(self, db: Session) -> None:
        # Arrange
        developer = DeveloperFactory()

        # Act & Assert
        with pytest.raises(HTTPException):
            user_invitation_code_service.generate(db, uuid4(), developer.id)

    def test_generate_revokes_previous_active_codes(self, db: Session) -> None:
        # Arrange
        developer = DeveloperFactory()
        user = UserFactory()
        first = user_invitation_code_service.generate(db, user.id, developer.id)

        # Act
        user_invitation_code_service.generate(db, user.id, developer.id)

        # Assert
        db_first = db.query(UserInvitationCode).filter(UserInvitationCode.id == first.id).first()
        assert db_first is not None
        assert db_first.revoked_at is not None

    def test_generate_does_not_revoke_other_users_codes(self, db: Session) -> None:
        # Arrange
        developer = DeveloperFactory()
        user_a = UserFactory()
        user_b = UserFactory()
        code_a = user_invitation_code_service.generate(db, user_a.id, developer.id)

        # Act
        user_invitation_code_service.generate(db, user_b.id, developer.id)

        # Assert
        db_code_a = db.query(UserInvitationCode).filter(UserInvitationCode.id == code_a.id).first()
        assert db_code_a is not None
        assert db_code_a.revoked_at is None


class TestRedeem:
    """Tests for redeem method."""

    def test_redeem_returns_tokens(self, db: Session) -> None:
        # Arrange
        developer = DeveloperFactory()
        user = UserFactory()
        generated = user_invitation_code_service.generate(db, user.id, developer.id)

        # Act
        result = user_invitation_code_service.redeem(db, generated.code)

        # Assert
        assert result.user_id == user.id
        assert result.access_token is not None
        assert result.refresh_token.startswith("rt-")
        assert result.token_type == "bearer"
        assert result.expires_in == settings.access_token_expire_minutes * 60

    def test_redeem_returns_sdk_scoped_token(self, db: Session) -> None:
        # Arrange
        developer = DeveloperFactory()
        user = UserFactory()
        generated = user_invitation_code_service.generate(db, user.id, developer.id)

        # Act
        result = user_invitation_code_service.redeem(db, generated.code)

        # Assert
        payload = jwt.decode(
            result.access_token, settings.secret_key, algorithms=[settings.algorithm], options={"verify_exp": False}
        )
        assert payload["scope"] == "sdk"
        assert payload["sub"] == str(user.id)
        assert payload["app_id"] == f"invite:{developer.id}"

    def test_redeem_marks_code_as_redeemed(self, db: Session) -> None:
        # Arrange
        developer = DeveloperFactory()
        user = UserFactory()
        generated = user_invitation_code_service.generate(db, user.id, developer.id)

        # Act
        user_invitation_code_service.redeem(db, generated.code)

        # Assert
        db_code = db.query(UserInvitationCode).filter(UserInvitationCode.id == generated.id).first()
        assert db_code is not None
        assert db_code.redeemed_at is not None

    def test_redeem_single_use(self, db: Session) -> None:
        # Arrange
        developer = DeveloperFactory()
        user = UserFactory()
        generated = user_invitation_code_service.generate(db, user.id, developer.id)
        user_invitation_code_service.redeem(db, generated.code)

        # Act & Assert
        with pytest.raises(HTTPException):
            user_invitation_code_service.redeem(db, generated.code)

    def test_redeem_invalid_code_raises(self, db: Session) -> None:
        # Act & Assert
        with pytest.raises(HTTPException):
            user_invitation_code_service.redeem(db, "ZZZZZZZZ")

    def test_redeem_revoked_code_raises(self, db: Session) -> None:
        # Arrange
        developer = DeveloperFactory()
        user = UserFactory()
        first = user_invitation_code_service.generate(db, user.id, developer.id)
        # Generate again to revoke the first
        user_invitation_code_service.generate(db, user.id, developer.id)

        # Act & Assert
        with pytest.raises(HTTPException):
            user_invitation_code_service.redeem(db, first.code)

    def test_redeem_expired_code_raises(self, db: Session) -> None:
        # Arrange
        developer = DeveloperFactory()
        user = UserFactory()
        expired = UserInvitationCode(
            id=uuid4(),
            code="XPRD2345",
            user_id=user.id,
            created_by_id=developer.id,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            redeemed_at=None,
            revoked_at=None,
            created_at=datetime.now(timezone.utc) - timedelta(days=8),
        )
        db.add(expired)
        db.flush()

        # Act & Assert
        with pytest.raises(HTTPException):
            user_invitation_code_service.redeem(db, "XPRD2345")

    def test_redeem_normalizes_to_uppercase(self, db: Session) -> None:
        # Arrange
        developer = DeveloperFactory()
        user = UserFactory()
        generated = user_invitation_code_service.generate(db, user.id, developer.id)

        # Act
        result = user_invitation_code_service.redeem(db, generated.code.lower())

        # Assert
        assert result.user_id == user.id
