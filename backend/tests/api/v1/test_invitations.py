"""Tests for the invitation endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import DeveloperFactory
from tests.utils import developer_auth_headers


class TestCreateInvitation:
    def test_refuses_an_email_that_already_belongs_to_a_developer(
        self, client: TestClient, db: Session, api_v1_prefix: str
    ) -> None:
        inviter = DeveloperFactory()
        DeveloperFactory(email="taken@example.com")

        response = client.post(
            f"{api_v1_prefix}/invitations",
            json={"email": "taken@example.com"},
            headers=developer_auth_headers(inviter.id),
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "A developer with this email already exists"
