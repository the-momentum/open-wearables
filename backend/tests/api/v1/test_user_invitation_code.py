"""Tests for user invitation code endpoints."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from dirty_equals import IsDatetime, IsStr, IsUUID
from jose import jwt
from redis.exceptions import ConnectionError as RedisConnectionError
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

    def test_redeem_accepts_display_form_in_any_case(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        # Arrange
        user = UserFactory()
        code = _generate(client, api_v1_prefix, user.id)["code"]

        # Act
        typed = f" {code[:4].lower()}-{code[4:]} "
        response = client.post(f"{api_v1_prefix}/invitation-code/redeem", json={"code": typed})

        # Assert
        assert response.status_code == 200
        assert response.json()["user_id"] == str(user.id)

    def test_redeem_validation_rejects_confusable_characters(
        self, client: TestClient, db: Session, api_v1_prefix: str
    ) -> None:
        # Act - 0 and 1 are not in the alphabet
        response = client.post(f"{api_v1_prefix}/invitation-code/redeem", json={"code": "ABCD-EF01"})

        # Assert
        assert response.status_code == 422


def _generate(client: TestClient, api_v1_prefix: str, user_id: object) -> dict:
    headers = developer_auth_headers(DeveloperFactory().id)
    response = client.post(f"{api_v1_prefix}/users/{user_id}/invitation-code", headers=headers)
    assert response.status_code == 201
    return response.json()


class TestGenerateShareableForms:
    """invite_url and qr_svg in the generate response."""

    def test_invite_url_carries_host_and_display_code_in_fragment(
        self, client: TestClient, db: Session, api_v1_prefix: str
    ) -> None:
        # Arrange
        user = UserFactory()

        # Act
        with (
            patch.object(settings, "api_base_url", "https://api.acmehealth.com"),
            patch.object(settings, "connect_app_link_base", "https://connect.openwearables.io/i"),
        ):
            data = _generate(client, api_v1_prefix, user.id)

        # Assert
        code = data["code"]
        assert data["invite_url"] == (
            f"https://connect.openwearables.io/i#v=1&h=api.acmehealth.com&c={code[:4]}-{code[4:]}"
        )
        assert data["qr_svg"].startswith("<svg")

    def test_invite_url_keeps_a_non_default_port(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        # Act
        with patch.object(settings, "api_base_url", "http://localhost:8000"):
            data = _generate(client, api_v1_prefix, UserFactory().id)

        # Assert
        assert "&h=localhost:8000&" in data["invite_url"]


class TestValidateInvitationCode:
    """Tests for POST /api/v1/invitation-code/validate"""

    def test_validate_does_not_use_the_code_up(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        # Arrange
        user = UserFactory()
        generated = _generate(client, api_v1_prefix, user.id)

        # Act
        first = client.post(f"{api_v1_prefix}/invitation-code/validate", json={"code": generated["code"]})
        second = client.post(f"{api_v1_prefix}/invitation-code/validate", json={"code": generated["code"]})
        redeem = client.post(f"{api_v1_prefix}/invitation-code/redeem", json={"code": generated["code"]})

        # Assert
        assert first.status_code == 200
        assert first.json() == {"expires_at": generated["expires_at"]}
        assert second.status_code == 200
        assert redeem.status_code == 200

    def test_validate_rejects_a_redeemed_code(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        # Arrange
        code = _generate(client, api_v1_prefix, UserFactory().id)["code"]
        client.post(f"{api_v1_prefix}/invitation-code/redeem", json={"code": code})

        # Act
        response = client.post(f"{api_v1_prefix}/invitation-code/validate", json={"code": code})

        # Assert
        assert response.status_code == 404

    def test_validate_rejects_an_unknown_code(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        # Act
        response = client.post(f"{api_v1_prefix}/invitation-code/validate", json={"code": "XPRD-2345"})

        # Assert
        assert response.status_code == 404


class TestInvitationCodeRateLimit:
    """Validate and redeem share a per-IP attempt budget."""

    def test_over_the_limit_returns_429_with_retry_after(
        self, client: TestClient, db: Session, api_v1_prefix: str
    ) -> None:
        # Arrange
        with patch.object(settings, "invitation_code_rate_limit_per_minute", 2):
            # Act
            first = client.post(f"{api_v1_prefix}/invitation-code/validate", json={"code": "XPRD-2345"})
            second = client.post(f"{api_v1_prefix}/invitation-code/redeem", json={"code": "XPRD-2345"})
            third = client.post(f"{api_v1_prefix}/invitation-code/validate", json={"code": "XPRD-2345"})

        # Assert
        assert first.status_code == 404
        assert second.status_code == 404
        assert third.status_code == 429
        assert 0 < int(third.headers["Retry-After"]) <= 60

    def test_redis_outage_lets_requests_through(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        # Arrange
        broken = MagicMock()
        broken.incr.side_effect = RedisConnectionError("down")

        # Act
        with (
            patch.object(settings, "invitation_code_rate_limit_per_minute", 0),
            patch("app.utils.rate_limit.get_redis_client", return_value=broken),
        ):
            response = client.post(f"{api_v1_prefix}/invitation-code/validate", json={"code": "XPRD-2345"})

        # Assert
        assert response.status_code == 404
