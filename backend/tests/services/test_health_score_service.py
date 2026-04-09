"""
Tests for HealthScoreService.

Tests cover:
- get_scores_with_filters delegates correctly
- get_latest_by_category
- get_latest_per_category
- bulk_create
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.schemas.enums import HealthScoreCategory, ProviderName
from app.schemas.model_crud.activities import HealthScoreCreate, HealthScoreQueryParams
from app.services.health_score_service import health_score_service
from tests.factories import DataSourceFactory, HealthScoreFactory, UserFactory


class TestHealthScoreServiceGetScores:
    def test_get_scores_with_filters_returns_user_scores(self, db: Session) -> None:
        user = UserFactory()
        data_source = DataSourceFactory(user=user)
        HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.SLEEP)
        HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.RECOVERY)

        results, total = health_score_service.get_scores_with_filters(db, user.id, HealthScoreQueryParams())

        assert total == 2

    def test_get_scores_with_filters_by_category(self, db: Session) -> None:
        user = UserFactory()
        data_source = DataSourceFactory(user=user)
        HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.SLEEP)
        HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.RECOVERY)

        results, total = health_score_service.get_scores_with_filters(
            db, user.id, HealthScoreQueryParams(category=HealthScoreCategory.SLEEP)
        )

        assert total == 1
        assert results[0].category == HealthScoreCategory.SLEEP

    def test_get_scores_with_filters_empty(self, db: Session) -> None:
        user = UserFactory()

        results, total = health_score_service.get_scores_with_filters(db, user.id, HealthScoreQueryParams())

        assert total == 0
        assert results == []


class TestHealthScoreServiceLatest:
    def test_get_latest_by_category(self, db: Session) -> None:
        user = UserFactory()
        data_source = DataSourceFactory(user=user)
        now = datetime.now(timezone.utc)
        HealthScoreFactory(
            data_source=data_source,
            category=HealthScoreCategory.SLEEP,
            recorded_at=now - timedelta(days=1),
            value=Decimal("70.00"),
        )
        latest = HealthScoreFactory(
            data_source=data_source, category=HealthScoreCategory.SLEEP, recorded_at=now, value=Decimal("90.00")
        )

        result = health_score_service.get_latest_by_category(db, user.id, HealthScoreCategory.SLEEP)

        assert result is not None
        assert result.id == latest.id

    def test_get_latest_by_category_wrong_category_returns_none(self, db: Session) -> None:
        user = UserFactory()
        data_source = DataSourceFactory(user=user)
        HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.SLEEP)

        result = health_score_service.get_latest_by_category(db, user.id, HealthScoreCategory.RECOVERY)

        assert result is None

    def test_get_latest_per_category(self, db: Session) -> None:
        user = UserFactory()
        data_source = DataSourceFactory(user=user)
        now = datetime.now(timezone.utc)
        HealthScoreFactory(
            data_source=data_source, category=HealthScoreCategory.SLEEP, recorded_at=now - timedelta(days=1)
        )
        HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.SLEEP, recorded_at=now)
        HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.RECOVERY, recorded_at=now)

        results = health_score_service.get_latest_per_category(db, user.id)

        assert len(results) == 2
        assert {s.category for s in results} == {HealthScoreCategory.SLEEP, HealthScoreCategory.RECOVERY}


class TestHealthScoreServiceBulkCreate:
    def test_bulk_create(self, db: Session) -> None:
        data_source = DataSourceFactory()
        now = datetime.now(timezone.utc)
        scores = [
            HealthScoreCreate(
                id=uuid4(),
                user_id=data_source.user_id,
                data_source_id=data_source.id,
                provider=ProviderName.GARMIN,
                category=HealthScoreCategory.SLEEP,
                value=Decimal("80.00"),
                recorded_at=now - timedelta(days=i),
            )
            for i in range(3)
        ]

        health_score_service.bulk_create(db, scores)
        db.commit()

        results, total = health_score_service.get_scores_with_filters(
            db,
            data_source.user_id,
            HealthScoreQueryParams(),
        )
        assert total == 3
