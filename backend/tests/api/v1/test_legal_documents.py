"""Tests for the instance's legal documents: settings, versioning, instance/info and acceptances."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import LegalAcceptance
from app.services.sdk_token_service import create_sdk_user_token
from tests.factories import ApiKeyFactory, UserFactory

POLICY = "https://acmehealth.com/privacy"
TERMS = "https://acmehealth.com/terms"


def _settings(client: TestClient, prefix: str, headers: dict[str, str], **fields: object) -> dict:
    response = client.patch(f"{prefix}/instance/settings", headers=headers, json=fields)
    assert response.status_code == 200, response.text
    return response.json()


def _sdk_headers(user_id: object) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_sdk_user_token('app', str(user_id))}"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TestLegalDocumentSettings:
    def test_saves_documents_and_shows_them_in_info(
        self, client: TestClient, db: Session, api_v1_prefix: str, auth_headers: dict[str, str]
    ) -> None:
        _settings(
            client, api_v1_prefix, auth_headers, privacy_policy_url=POLICY, terms_url=TERMS, require_acceptance=True
        )

        info = client.get(f"{api_v1_prefix}/instance/info").json()

        assert info["privacy_policy_url"] == POLICY
        assert info["terms_url"] == TERMS
        assert info["require_acceptance"] is True
        assert info["legal_documents_version"] == 2

    def test_url_change_bumps_the_version_other_changes_do_not(
        self, client: TestClient, db: Session, api_v1_prefix: str, auth_headers: dict[str, str]
    ) -> None:
        assert _settings(client, api_v1_prefix, auth_headers, privacy_policy_url=POLICY)["legal_documents_version"] == 2
        # The same URL again, another field, and the acceptance flag leave the version alone.
        assert _settings(client, api_v1_prefix, auth_headers, privacy_policy_url=POLICY)["legal_documents_version"] == 2
        assert _settings(client, api_v1_prefix, auth_headers, organization_name="Acme")["legal_documents_version"] == 2
        assert _settings(client, api_v1_prefix, auth_headers, require_acceptance=True)["legal_documents_version"] == 2

        assert _settings(client, api_v1_prefix, auth_headers, terms_url=TERMS)["legal_documents_version"] == 3
        assert _settings(client, api_v1_prefix, auth_headers, terms_url=None)["legal_documents_version"] == 4

    def test_manual_bump(
        self, client: TestClient, db: Session, api_v1_prefix: str, auth_headers: dict[str, str]
    ) -> None:
        _settings(client, api_v1_prefix, auth_headers, privacy_policy_url=POLICY)

        body = _settings(client, api_v1_prefix, auth_headers, bump_legal_documents_version=True)

        assert body["legal_documents_version"] == 3
        assert body["privacy_policy_url"] == POLICY

    def test_acceptance_needs_a_document(
        self, client: TestClient, db: Session, api_v1_prefix: str, auth_headers: dict[str, str]
    ) -> None:
        url = f"{api_v1_prefix}/instance/settings"
        assert client.patch(url, headers=auth_headers, json={"require_acceptance": True}).status_code == 400

        _settings(client, api_v1_prefix, auth_headers, privacy_policy_url=POLICY, require_acceptance=True)
        assert client.patch(url, headers=auth_headers, json={"privacy_policy_url": None}).status_code == 400
        # Turning the requirement off and clearing the document in one request is fine.
        body = _settings(client, api_v1_prefix, auth_headers, privacy_policy_url="", require_acceptance=False)
        assert body["privacy_policy_url"] is None

    def test_rejects_plain_http_documents(
        self, client: TestClient, db: Session, api_v1_prefix: str, auth_headers: dict[str, str]
    ) -> None:
        url = f"{api_v1_prefix}/instance/settings"

        assert client.patch(url, headers=auth_headers, json={"privacy_policy_url": "http://a.com/p"}).status_code == 400
        assert client.patch(url, headers=auth_headers, json={"terms_url": "not a url"}).status_code == 400


class TestLegalAcceptance:
    def _url(self, prefix: str, user_id: object) -> str:
        return f"{prefix}/sdk/users/{user_id}/legal-acceptance"

    def test_records_the_current_version_once(
        self, client: TestClient, db: Session, api_v1_prefix: str, auth_headers: dict[str, str]
    ) -> None:
        _settings(client, api_v1_prefix, auth_headers, privacy_policy_url=POLICY, require_acceptance=True)
        user = UserFactory()
        accepted_at = _now()
        payload = {"documents_version": 2, "accepted_at": accepted_at}

        first = client.post(self._url(api_v1_prefix, user.id), headers=_sdk_headers(user.id), json=payload)
        retry = client.post(self._url(api_v1_prefix, user.id), headers=_sdk_headers(user.id), json=payload)

        assert first.status_code == 201
        assert retry.status_code == 200
        assert retry.json()["id"] == first.json()["id"]
        assert first.json()["privacy_policy_url"] == POLICY
        assert first.json()["terms_url"] is None
        assert db.query(LegalAcceptance).filter(LegalAcceptance.user_id == user.id).count() == 1

    def test_stale_version_is_a_conflict(
        self, client: TestClient, db: Session, api_v1_prefix: str, auth_headers: dict[str, str]
    ) -> None:
        _settings(client, api_v1_prefix, auth_headers, privacy_policy_url=POLICY)
        _settings(client, api_v1_prefix, auth_headers, bump_legal_documents_version=True)
        user = UserFactory()

        response = client.post(
            self._url(api_v1_prefix, user.id),
            headers=_sdk_headers(user.id),
            json={"documents_version": 2, "accepted_at": _now()},
        )

        assert response.status_code == 409

    def test_no_documents_is_a_conflict(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        user = UserFactory()

        response = client.post(
            self._url(api_v1_prefix, user.id),
            headers=_sdk_headers(user.id),
            json={"documents_version": 1, "accepted_at": _now()},
        )

        assert response.status_code == 409

    def test_rejects_a_future_timestamp(
        self, client: TestClient, db: Session, api_v1_prefix: str, auth_headers: dict[str, str]
    ) -> None:
        _settings(client, api_v1_prefix, auth_headers, privacy_policy_url=POLICY)
        user = UserFactory()
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

        response = client.post(
            self._url(api_v1_prefix, user.id),
            headers=_sdk_headers(user.id),
            json={"documents_version": 2, "accepted_at": future},
        )

        assert response.status_code == 400

    def test_only_the_users_own_token(
        self, client: TestClient, db: Session, api_v1_prefix: str, auth_headers: dict[str, str]
    ) -> None:
        _settings(client, api_v1_prefix, auth_headers, privacy_policy_url=POLICY)
        user = UserFactory()
        payload = {"documents_version": 2, "accepted_at": _now()}
        api_key = ApiKeyFactory()

        other_user = client.post(
            self._url(api_v1_prefix, user.id), headers=_sdk_headers(UserFactory().id), json=payload
        )
        with_api_key = client.post(
            self._url(api_v1_prefix, user.id), headers={"X-Open-Wearables-API-Key": api_key.plain_key}, json=payload
        )
        anonymous = client.post(self._url(api_v1_prefix, user.id), json=payload)

        assert other_user.status_code == 403
        assert with_api_key.status_code == 403
        assert anonymous.status_code == 401

    def test_developer_lists_acceptances_newest_first_and_they_go_with_the_user(
        self, client: TestClient, db: Session, api_v1_prefix: str, auth_headers: dict[str, str]
    ) -> None:
        _settings(client, api_v1_prefix, auth_headers, privacy_policy_url=POLICY)
        user = UserFactory()
        client.post(
            self._url(api_v1_prefix, user.id),
            headers=_sdk_headers(user.id),
            json={"documents_version": 2, "accepted_at": _now()},
        )
        _settings(client, api_v1_prefix, auth_headers, terms_url=TERMS)
        client.post(
            self._url(api_v1_prefix, user.id),
            headers=_sdk_headers(user.id),
            json={"documents_version": 3, "accepted_at": _now()},
        )

        listed = client.get(f"{api_v1_prefix}/users/{user.id}/legal-acceptances", headers=auth_headers)

        assert listed.status_code == 200
        assert [a["documents_version"] for a in listed.json()] == [3, 2]
        assert listed.json()[0]["terms_url"] == TERMS
        assert client.get(f"{api_v1_prefix}/users/{user.id}/legal-acceptances").status_code == 401

        client.delete(f"{api_v1_prefix}/users/{user.id}", headers=auth_headers)
        db.expire_all()
        assert db.query(LegalAcceptance).filter(LegalAcceptance.user_id == user.id).count() == 0
