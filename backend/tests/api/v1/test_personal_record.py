"""
Tests for the personal record endpoints.

- GET /api/v1/users/{user_id}/personal-record
- PUT /api/v1/users/{user_id}/personal-record
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import PersonalRecord, User
from tests.factories import (
    DataPointSeriesFactory,
    DataSourceFactory,
    PersonalRecordFactory,
    SeriesTypeDefinitionFactory,
)


def record_url(api_v1_prefix: str, user_id: UUID) -> str:
    return f"{api_v1_prefix}/users/{user_id}/personal-record"


class TestGetPersonalRecord:
    def test_without_record_returns_nulls(
        self, client: TestClient, user: User, api_key_header: dict[str, str], api_v1_prefix: str
    ) -> None:
        response = client.get(record_url(api_v1_prefix, user.id), headers=api_key_header)

        assert response.status_code == 200
        assert response.json() == {"user_id": str(user.id), "birth_date": None, "gender": None, "sex": None}

    def test_returns_stored_values(
        self, client: TestClient, user: User, api_key_header: dict[str, str], api_v1_prefix: str
    ) -> None:
        PersonalRecordFactory(user=user, birth_date=date(1990, 5, 1), gender="female", sex=False)

        response = client.get(record_url(api_v1_prefix, user.id), headers=api_key_header)

        assert response.status_code == 200
        assert response.json() == {
            "user_id": str(user.id),
            "birth_date": "1990-05-01",
            "gender": "female",
            "sex": "female",
        }

    def test_reads_stored_true_as_male(
        self, client: TestClient, user: User, api_key_header: dict[str, str], api_v1_prefix: str
    ) -> None:
        PersonalRecordFactory(user=user, sex=True)

        response = client.get(record_url(api_v1_prefix, user.id), headers=api_key_header)

        assert response.json()["sex"] == "male"

    def test_unknown_user_returns_404(
        self, client: TestClient, api_key_header: dict[str, str], api_v1_prefix: str
    ) -> None:
        response = client.get(record_url(api_v1_prefix, uuid4()), headers=api_key_header)

        assert response.status_code == 404

    def test_requires_api_key(self, client: TestClient, user: User, api_v1_prefix: str) -> None:
        response = client.get(record_url(api_v1_prefix, user.id))

        assert response.status_code == 401


class TestPutPersonalRecord:
    def test_creates_record(
        self, client: TestClient, db: Session, user: User, api_key_header: dict[str, str], api_v1_prefix: str
    ) -> None:
        response = client.put(
            record_url(api_v1_prefix, user.id),
            json={"birth_date": "1990-05-01", "gender": "female", "sex": "male"},
            headers=api_key_header,
        )

        assert response.status_code == 200
        assert response.json() == {
            "user_id": str(user.id),
            "birth_date": "1990-05-01",
            "gender": "female",
            "sex": "male",
        }
        record = db.query(PersonalRecord).filter(PersonalRecord.user_id == user.id).one()
        assert record.birth_date == date(1990, 5, 1)
        assert record.gender == "female"
        assert record.sex is True  # stored as a boolean: True = male, False = female

    def test_replaces_whole_record(
        self, client: TestClient, db: Session, user: User, api_key_header: dict[str, str], api_v1_prefix: str
    ) -> None:
        PersonalRecordFactory(user=user, birth_date=date(1990, 5, 1), gender="female", sex=False)

        response = client.put(
            record_url(api_v1_prefix, user.id),
            json={"birth_date": "1991-01-01"},
            headers=api_key_header,
        )

        assert response.status_code == 200
        assert response.json() == {"user_id": str(user.id), "birth_date": "1991-01-01", "gender": None, "sex": None}
        assert db.query(PersonalRecord).filter(PersonalRecord.user_id == user.id).count() == 1

    def test_unknown_user_returns_404(
        self, client: TestClient, api_key_header: dict[str, str], api_v1_prefix: str
    ) -> None:
        response = client.put(
            record_url(api_v1_prefix, uuid4()),
            json={"birth_date": "1990-05-01"},
            headers=api_key_header,
        )

        assert response.status_code == 404

    def test_future_birth_date_returns_400(
        self, client: TestClient, user: User, api_key_header: dict[str, str], api_v1_prefix: str
    ) -> None:
        # Two days ahead, so the test cannot fail when it runs across midnight UTC.
        future = datetime.now(timezone.utc).date() + timedelta(days=2)

        response = client.put(
            record_url(api_v1_prefix, user.id),
            json={"birth_date": future.isoformat()},
            headers=api_key_header,
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "birth_date cannot be in the future"}

    def test_unknown_gender_returns_400(
        self, client: TestClient, user: User, api_key_header: dict[str, str], api_v1_prefix: str
    ) -> None:
        response = client.put(
            record_url(api_v1_prefix, user.id),
            json={"gender": "unknown"},
            headers=api_key_header,
        )

        assert response.status_code == 400

    def test_unknown_sex_returns_400(
        self, client: TestClient, user: User, api_key_header: dict[str, str], api_v1_prefix: str
    ) -> None:
        response = client.put(
            record_url(api_v1_prefix, user.id),
            json={"sex": "other"},
            headers=api_key_header,
        )

        assert response.status_code == 400

    def test_requires_api_key(self, client: TestClient, user: User, api_v1_prefix: str) -> None:
        response = client.put(record_url(api_v1_prefix, user.id), json={"birth_date": "1990-05-01"})

        assert response.status_code == 401

    def test_birth_date_feeds_body_summary_age(
        self, client: TestClient, user: User, api_key_header: dict[str, str], api_v1_prefix: str
    ) -> None:
        # The body summary returns null without any body data, so give it one weight reading.
        mapping = DataSourceFactory(user=user, source="apple")
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=SeriesTypeDefinitionFactory.get_or_create_weight(),
            value=Decimal("70.0"),
            recorded_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        client.put(record_url(api_v1_prefix, user.id), json={"birth_date": "1990-06-15"}, headers=api_key_header)

        response = client.get(f"{api_v1_prefix}/users/{user.id}/summaries/body", headers=api_key_header)

        today = datetime.now(timezone.utc).date()
        expected_age = today.year - 1990 - ((today.month, today.day) < (6, 15))
        assert response.status_code == 200
        assert response.json()["slow_changing"]["age"] == expected_age
