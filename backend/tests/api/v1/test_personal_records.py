from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import ApiKeyFactory, DeveloperFactory, UserFactory
from tests.utils import api_key_headers


def _headers() -> dict[str, str]:
    developer = DeveloperFactory(email="pr-test@example.com", password="test123")
    api_key = ApiKeyFactory(developer=developer)
    return api_key_headers(api_key.id)


class TestUpsertPersonalRecord:
    def test_creates_when_absent(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        user = UserFactory()
        headers = _headers()
        payload = {"birth_date": "1990-05-17", "gender": "male"}

        response = client.put(f"{api_v1_prefix}/users/{user.id}/personal-record", json=payload, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == str(user.id)
        assert data["birth_date"] == "1990-05-17"
        assert data["gender"] == "male"
        assert "id" in data

    def test_updates_when_present(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        user = UserFactory()
        headers = _headers()
        url = f"{api_v1_prefix}/users/{user.id}/personal-record"

        first = client.put(url, json={"birth_date": "1990-05-17"}, headers=headers)
        assert first.status_code == 201
        first_id = first.json()["id"]

        second = client.put(url, json={"birth_date": "1985-06-06", "gender": "female"}, headers=headers)
        assert second.status_code == 200
        data = second.json()
        assert data["id"] == first_id  # same row
        assert data["birth_date"] == "1985-06-06"
        assert data["gender"] == "female"

    def test_unknown_user_returns_404(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        headers = _headers()
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.put(
            f"{api_v1_prefix}/users/{fake_id}/personal-record",
            json={"birth_date": "1990-05-17"},
            headers=headers,
        )
        assert response.status_code == 404

    def test_future_birth_date_returns_400(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        user = UserFactory()
        headers = _headers()
        future = (date.today() + timedelta(days=1)).isoformat()
        response = client.put(
            f"{api_v1_prefix}/users/{user.id}/personal-record",
            json={"birth_date": future},
            headers=headers,
        )
        assert response.status_code == 400

    def test_unauthorized_without_api_key(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        user = UserFactory()
        response = client.put(
            f"{api_v1_prefix}/users/{user.id}/personal-record",
            json={"birth_date": "1990-05-17"},
        )
        assert response.status_code == 401


class TestGetPersonalRecord:
    def test_returns_record(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        user = UserFactory()
        headers = _headers()
        url = f"{api_v1_prefix}/users/{user.id}/personal-record"
        client.put(url, json={"birth_date": "1990-05-17", "gender": "male"}, headers=headers)

        response = client.get(url, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == str(user.id)
        assert data["birth_date"] == "1990-05-17"

    def test_404_when_no_record(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        user = UserFactory()
        headers = _headers()
        response = client.get(f"{api_v1_prefix}/users/{user.id}/personal-record", headers=headers)
        assert response.status_code == 404

    def test_unauthorized_without_api_key(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        user = UserFactory()
        response = client.get(f"{api_v1_prefix}/users/{user.id}/personal-record")
        assert response.status_code == 401
