"""Tests for the invitation endpoints."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Invitation
from app.schemas.model_crud.user_management import InvitationStatus
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

        assert response.status_code == 409
        assert response.json()["detail"] == "A developer with this email already exists"


class TestAcceptInvitation:
    @pytest.mark.parametrize(
        ("invitation_status", "expires_in", "code"),
        [
            (InvitationStatus.ACCEPTED, timedelta(days=1), "INVITATION_ALREADY_ACCEPTED"),
            (InvitationStatus.EXPIRED, timedelta(days=1), "INVITATION_EXPIRED"),
            (InvitationStatus.SENT, timedelta(days=-1), "INVITATION_EXPIRED"),
            (InvitationStatus.REVOKED, timedelta(days=1), "INVITATION_WITHDRAWN"),
            (InvitationStatus.FAILED, timedelta(days=1), "INVITATION_WITHDRAWN"),
        ],
    )
    def test_a_dead_link_says_why_in_its_code(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        invitation_status: InvitationStatus,
        expires_in: timedelta,
        code: str,
    ) -> None:
        """The portal's accept page tells the person what happened to their invitation."""
        db.add(
            Invitation(
                id=uuid4(),
                email="jane@example.com",
                token="invite-token",
                status=invitation_status,
                expires_at=datetime.now(timezone.utc) + expires_in,
            )
        )
        db.flush()

        response = client.post(
            f"{api_v1_prefix}/invitations/accept",
            json={"token": "invite-token", "first_name": "Jane", "last_name": "Doe", "password": "a-long-password"},
        )

        assert response.status_code == 400
        assert response.json()["code"] == code
