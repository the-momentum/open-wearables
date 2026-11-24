"""Tests for user invitation code endpoints."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dirty_equals import IsDatetime, IsStr, IsUUID
from jose import jwt
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.config import settings
from app.models.user_invitation_code import UserInvitationCode
from tests.factories import DeveloperFactory, UserFactory
from tests.utils import developer_auth_headers


class TestGenerateInvitationCode:
    """Tests for POST /api/v1/users/{user_id}/invitation-code"""

    def test_generate_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        # Arrange
        developer = DeveloperFactory()
        user = UserFactory()
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.post(f"{api_v1_prefix}/users/{user.id}/invitation-code", headers=headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data == {
            "id": IsUUID,
            "code": IsStr(min_length=8, max_length=8),
            "user_id": str(user.id),
            "expires_at": IsDatetime(iso_string=True),
            "created_at": IsDatetime(iso_string=True),
        }

    def test_generate_requires_auth(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        # Arrange
        user = UserFactory()

        # Act
        response = client.post(f"{api_v1_prefix}/users/{user.id}/invitation-code")

        # Assert
        assert response.status_code == 401

    def test_generate_nonexistent_user_returns_404(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        # Arrange
        developer = DeveloperFactory()
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.post(f"{api_v1_prefix}/users/{uuid4()}/invitation-code", headers=headers)

        # Assert
        assert response.status_code == 404

    def test_generate_revokes_previous_codes(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        # Arrange
        developer = DeveloperFactory()
        user = UserFactory()
        headers = developer_auth_headers(developer.id)

        # Act - generate two codes
        response1 = client.post(f"{api_v1_prefix}/users/{user.id}/invitation-code", headers=headers)
        code1 = response1.json()["code"]
        response2 = client.post(f"{api_v1_prefix}/users/{user.id}/invitation-code", headers=headers)
        code2 = response2.json()["code"]

        # Assert - first code should be revoked
        assert response2.status_code == 201
        redeem1 = client.post(f"{api_v1_prefix}/invitation-code/redeem", json={"code": code1})
        assert redeem1.status_code == 404

        redeem2 = client.post(f"{api_v1_prefix}/invitation-code/redeem", json={"code": code2})
        assert redeem2.status_code == 200


class TestRedeemInvitationCode:
    """Tests for POST /api/v1/invitation-code/redeem"""

    def test_redeem_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        # Arrange
        developer = DeveloperFactory()
        user = UserFactory()
        headers = developer_auth_headers(developer.id)
        gen_response = client.post(f"{api_v1_prefix}/users/{user.id}/invitation-code", headers=headers)
        code = gen_response.json()["code"]

        # Act
        response = client.post(f"{api_v1_prefix}/invitation-code/redeem", json={"code": code})

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data == {
            "user_id": str(user.id),
            "access_token": IsStr,
            "refresh_token": IsStr(regex=r"rt-.*"),
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
            "password_change": None,
        }

    def test_redeem_returns_sdk_token(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        # Arrange
        developer = DeveloperFactory()
        user = UserFactory()
        headers = developer_auth_headers(developer.id)
        gen_response = client.post(f"{api_v1_prefix}/users/{user.id}/invitation-code", headers=headers)
        code = gen_response.json()["code"]

        # Act
        response = client.post(f"{api_v1_prefix}/invitation-code/redeem", json={"code": code})

        # Assert
        token = response.json()["access_token"]
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm], options={"verify_exp": False})
        assert payload["scope"] == "sdk"
        assert payload["sub"] == str(user.id)
        assert payload["app_id"] == f"invite:{developer.id}"

    def test_redeem_single_use(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        # Arrange
        developer = DeveloperFactory()
        user = UserFactory()
        headers = developer_auth_headers(developer.id)
        gen_response = client.post(f"{api_v1_prefix}/users/{user.id}/invitation-code", headers=headers)
        code = gen_response.json()["code"]

        # Act
        first_redeem = client.post(f"{api_v1_prefix}/invitation-code/redeem", json={"code": code})
        second_redeem = client.post(f"{api_v1_prefix}/invitation-code/redeem", json={"code": code})

        # Assert
        assert first_redeem.status_code == 200
        assert second_redeem.status_code == 404

    def test_redeem_invalid_code(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        # Act
        response = client.post(f"{api_v1_prefix}/invitation-code/redeem", json={"code": "ZZZZZZZZ"})

        # Assert
        assert response.status_code == 404

    def test_redeem_expired_code(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        # Arrange - create expired code directly in DB
        developer = DeveloperFactory()
        user = UserFactory()
        expired_code = UserInvitationCode(
            id=uuid4(),
            code="XPRD2345",
            user_id=user.id,
            created_by_id=developer.id,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            redeemed_at=None,
            revoked_at=None,
            created_at=datetime.now(timezone.utc) - timedelta(days=8),
        )
        db.add(expired_code)
        db.flush()

        # Act
        response = client.post(f"{api_v1_prefix}/invitation-code/redeem", json={"code": "XPRD2345"})

        # Assert
        assert response.status_code == 404

    def test_redeem_validation_rejects_short_code(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        # Act
        response = client.post(f"{api_v1_prefix}/invitation-code/redeem", json={"code": "ABC"})

        # Assert
        assert response.status_code == 422

    def test_redeem_validation_rejects_lowercase(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        # Act
        response = client.post(f"{api_v1_prefix}/invitation-code/redeem", json={"code": "abcdefgh"})

        # Assert
        assert response.status_code == 422
