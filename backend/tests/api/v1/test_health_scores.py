"""
Tests for health scores endpoint.

Tests cover:
- GET /api/v1/users/{user_id}/health-scores
- Filtering by category, provider, date range
- Authentication
- Empty results
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ProviderPriority
from app.repositories import ProviderPriorityRepository
from app.schemas.enums import HealthScoreCategory, ProviderName
from tests.factories import ApiKeyFactory, DataSourceFactory, HealthScoreFactory, UserFactory
from tests.utils import api_key_headers


class TestHealthScoresEndpoint:
    def test_one_ow_score_per_day_with_its_source(self, client: TestClient, db: Session) -> None:
        priorities = ProviderPriorityRepository(ProviderPriority)
        priorities.upsert(db, ProviderName.GARMIN, 1)
        priorities.upsert(db, ProviderName.OURA, 2)
        user = UserFactory()
        night = datetime(2026, 9, 24, 7, tzinfo=timezone.utc)
        garmin = DataSourceFactory(user=user, provider=ProviderName.GARMIN)
        oura = DataSourceFactory(user=user, provider=ProviderName.OURA)
        # Oura first, so the pick can't come from the order of writes
        HealthScoreFactory(data_source=oura, provider=ProviderName.INTERNAL, recorded_at=night)
        garmin_ow = HealthScoreFactory(data_source=garmin, provider=ProviderName.INTERNAL, recorded_at=night)
        garmin_own = HealthScoreFactory(
            data_source_id=None, user_id=user.id, provider=ProviderName.GARMIN, recorded_at=night
        )
        # The next day only Oura has a score, so it is the one returned
        oura_next_day = HealthScoreFactory(
            data_source=oura, provider=ProviderName.INTERNAL, recorded_at=night + timedelta(days=1)
        )
        headers = api_key_headers(ApiKeyFactory().plain_key)

        picked = client.get(f"/api/v1/users/{user.id}/health-scores", headers=headers).json()["data"]

        assert sorted(score["id"] for score in picked) == sorted(
            [str(garmin_ow.id), str(garmin_own.id), str(oura_next_day.id)]
        )
        assert {
            (score["provider"], score["recorded_at"][:10], (score["source"] or {}).get("provider")) for score in picked
        } == {
            ("internal", "2026-09-24", "garmin"),
            ("garmin", "2026-09-24", None),
            ("internal", "2026-09-25", "oura"),
        }

    def test_list_health_scores_success(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        data_source = DataSourceFactory(user=user)
        score1 = HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.SLEEP)
        score2 = HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.RECOVERY)
        api_key = ApiKeyFactory()

        response = client.get(
            f"/api/v1/users/{user.id}/health-scores",
            headers=api_key_headers(api_key.plain_key),
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 2
        assert any(s["id"] == str(score1.id) for s in data)
        assert any(s["id"] == str(score2.id) for s in data)

    def test_list_health_scores_empty(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        api_key = ApiKeyFactory()

        response = client.get(
            f"/api/v1/users/{user.id}/health-scores",
            headers=api_key_headers(api_key.plain_key),
        )

        assert response.status_code == 200
        assert response.json()["data"] == []
        assert response.json()["pagination"]["total_count"] == 0

    def test_list_health_scores_filter_by_category(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        data_source = DataSourceFactory(user=user)
        sleep_score = HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.SLEEP)
        HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.RECOVERY)
        api_key = ApiKeyFactory()

        response = client.get(
            f"/api/v1/users/{user.id}/health-scores",
            headers=api_key_headers(api_key.plain_key),
            params={"category": "sleep"},
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == str(sleep_score.id)

    def test_list_health_scores_filter_by_provider(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        data_source = DataSourceFactory(user=user)
        garmin_score = HealthScoreFactory(data_source=data_source, provider=ProviderName.GARMIN)
        HealthScoreFactory(data_source=data_source, provider=ProviderName.OURA)
        api_key = ApiKeyFactory()

        response = client.get(
            f"/api/v1/users/{user.id}/health-scores",
            headers=api_key_headers(api_key.plain_key),
            params={"provider": "garmin"},
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == str(garmin_score.id)

    def test_list_health_scores_filter_by_date_range(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        data_source = DataSourceFactory(user=user)
        now = datetime.now(timezone.utc)
        HealthScoreFactory(data_source=data_source, recorded_at=now - timedelta(days=1))
        HealthScoreFactory(data_source=data_source, recorded_at=now - timedelta(days=10))
        api_key = ApiKeyFactory()

        response = client.get(
            f"/api/v1/users/{user.id}/health-scores",
            headers=api_key_headers(api_key.plain_key),
            params={
                "start_date": (now - timedelta(days=3)).isoformat(),
                "end_date": now.isoformat(),
            },
        )

        assert response.status_code == 200
        assert len(response.json()["data"]) == 1

    def test_list_health_scores_requires_auth(self, client: TestClient, db: Session) -> None:
        user = UserFactory()

        response = client.get(f"/api/v1/users/{user.id}/health-scores")

        assert response.status_code == 401

    def test_list_health_scores_only_returns_own_user_scores(self, client: TestClient, db: Session) -> None:
        user_a = UserFactory()
        user_b = UserFactory()
        HealthScoreFactory(data_source=DataSourceFactory(user=user_a))
        HealthScoreFactory(data_source=DataSourceFactory(user=user_b))
        api_key = ApiKeyFactory()

        response = client.get(
            f"/api/v1/users/{user_a.id}/health-scores",
            headers=api_key_headers(api_key.plain_key),
        )

        assert response.status_code == 200
        assert len(response.json()["data"]) == 1
