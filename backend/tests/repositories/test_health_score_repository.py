"""
Tests for HealthScoreRepository.

Tests cover:
- Basic CRUD via CrudRepository base
- get_with_filters: category, provider, date range, user scoping
- get_latest_by_category
- get_latest_per_category
- bulk_create with on_conflict_do_nothing
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import HealthScore
from app.repositories.health_score_repository import HealthScoreRepository
from app.schemas.enums import HealthScoreCategory, ProviderName
from app.schemas.model_crud.activities import HealthScoreCreate, HealthScoreQueryParams
from tests.factories import DataSourceFactory, HealthScoreFactory, UserFactory


@pytest.fixture
def repo() -> HealthScoreRepository:
    return HealthScoreRepository(HealthScore)


class TestHealthScoreRepositoryCreate:
    def test_create(self, db: Session, repo: HealthScoreRepository) -> None:
        data_source = DataSourceFactory()
        score = HealthScoreCreate(
            id=uuid4(),
            user_id=data_source.user_id,
            data_source_id=data_source.id,
            provider=ProviderName.GARMIN,
            category=HealthScoreCategory.SLEEP,
            value=Decimal("82.00"),
            qualifier="GOOD",
            recorded_at=datetime.now(timezone.utc),
        )

        result = repo.create(db, score)

        assert result.id == score.id
        assert result.category == HealthScoreCategory.SLEEP
        assert result.value == Decimal("82.00")
        assert result.qualifier == "GOOD"

    def test_create_duplicate_returns_existing(self, db: Session, repo: HealthScoreRepository) -> None:
        recorded_at = datetime.now(timezone.utc)
        data_source = DataSourceFactory()
        score = HealthScoreCreate(
            id=uuid4(),
            user_id=data_source.user_id,
            data_source_id=data_source.id,
            provider=ProviderName.GARMIN,
            category=HealthScoreCategory.SLEEP,
            value=Decimal("82.00"),
            recorded_at=recorded_at,
        )
        repo.create(db, score)

        duplicate = HealthScoreCreate(
            id=uuid4(),
            user_id=data_source.user_id,
            data_source_id=data_source.id,
            provider=ProviderName.GARMIN,
            category=HealthScoreCategory.SLEEP,
            value=Decimal("90.00"),
            recorded_at=recorded_at,
        )
        result = repo.create(db, duplicate)

        assert result.id == score.id
        assert result.value == Decimal("82.00")


class TestHealthScoreRepositoryGetWithFilters:
    def test_filter_by_category(self, db: Session, repo: HealthScoreRepository) -> None:
        user = UserFactory()
        data_source = DataSourceFactory(user=user)
        HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.SLEEP)
        HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.SLEEP)
        HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.RECOVERY)

        results, total = repo.get_with_filters(db, user.id, HealthScoreQueryParams(category=HealthScoreCategory.SLEEP))

        assert total == 2
        assert all(s.category == HealthScoreCategory.SLEEP for s in results)

    def test_filter_by_provider(self, db: Session, repo: HealthScoreRepository) -> None:
        user = UserFactory()
        data_source = DataSourceFactory(user=user)
        HealthScoreFactory(data_source=data_source, provider=ProviderName.GARMIN)
        HealthScoreFactory(data_source=data_source, provider=ProviderName.OURA)

        results, total = repo.get_with_filters(db, user.id, HealthScoreQueryParams(provider=ProviderName.GARMIN))

        assert total == 1
        assert results[0].provider == ProviderName.GARMIN

    def test_filter_by_date_range(self, db: Session, repo: HealthScoreRepository) -> None:
        user = UserFactory()
        data_source = DataSourceFactory(user=user)
        now = datetime.now(timezone.utc)
        HealthScoreFactory(data_source=data_source, recorded_at=now - timedelta(days=1))
        HealthScoreFactory(data_source=data_source, recorded_at=now - timedelta(days=5))
        HealthScoreFactory(data_source=data_source, recorded_at=now - timedelta(days=10))

        results, total = repo.get_with_filters(
            db,
            user.id,
            HealthScoreQueryParams(
                start_datetime=now - timedelta(days=6),
                end_datetime=now,
            ),
        )

        assert total == 2

    def test_scoped_to_user(self, db: Session, repo: HealthScoreRepository) -> None:
        user_a = UserFactory()
        user_b = UserFactory()
        HealthScoreFactory(data_source=DataSourceFactory(user=user_a))
        HealthScoreFactory(data_source=DataSourceFactory(user=user_b))

        results, total = repo.get_with_filters(db, user_a.id, HealthScoreQueryParams())

        assert total == 1


class TestHealthScoreRepositoryLatest:
    def test_get_latest_by_category(self, db: Session, repo: HealthScoreRepository) -> None:
        user = UserFactory()
        data_source = DataSourceFactory(user=user)
        now = datetime.now(timezone.utc)
        HealthScoreFactory(
            data_source=data_source,
            category=HealthScoreCategory.SLEEP,
            recorded_at=now - timedelta(days=2),
            value=Decimal("70.00"),
        )
        latest = HealthScoreFactory(
            data_source=data_source, category=HealthScoreCategory.SLEEP, recorded_at=now, value=Decimal("85.00")
        )

        result = repo.get_latest_by_category(db, user.id, HealthScoreCategory.SLEEP)

        assert result is not None
        assert result.id == latest.id
        assert result.value == Decimal("85.00")

    def test_get_latest_by_category_returns_none_when_missing(self, db: Session, repo: HealthScoreRepository) -> None:
        user = UserFactory()

        result = repo.get_latest_by_category(db, user.id, HealthScoreCategory.RECOVERY)

        assert result is None

    def test_get_latest_per_category(self, db: Session, repo: HealthScoreRepository) -> None:
        user = UserFactory()
        data_source = DataSourceFactory(user=user)
        now = datetime.now(timezone.utc)
        HealthScoreFactory(
            data_source=data_source, category=HealthScoreCategory.SLEEP, recorded_at=now - timedelta(days=1)
        )
        HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.SLEEP, recorded_at=now)
        HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.RECOVERY, recorded_at=now)

        results = repo.get_latest_per_category(db, user.id)

        categories = {s.category for s in results}
        assert categories == {HealthScoreCategory.SLEEP, HealthScoreCategory.RECOVERY}
        assert len(results) == 2


class TestHealthScoreRepositoryBulkCreate:
    def test_bulk_create(self, db: Session, repo: HealthScoreRepository) -> None:
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

        repo.bulk_create(db, scores)
        db.commit()

        results = db.query(HealthScore).filter(HealthScore.data_source_id == data_source.id).all()
        assert len(results) == 3

    def test_bulk_create_ignores_duplicates(self, db: Session, repo: HealthScoreRepository) -> None:
        data_source = DataSourceFactory()
        recorded_at = datetime.now(timezone.utc)
        original = HealthScoreCreate(
            id=uuid4(),
            user_id=data_source.user_id,
            data_source_id=data_source.id,
            provider=ProviderName.GARMIN,
            category=HealthScoreCategory.SLEEP,
            value=Decimal("80.00"),
            recorded_at=recorded_at,
        )
        repo.bulk_create(db, [original])
        db.commit()

        duplicate = HealthScoreCreate(
            id=uuid4(),
            user_id=data_source.user_id,
            data_source_id=data_source.id,
            provider=ProviderName.GARMIN,
            category=HealthScoreCategory.SLEEP,
            value=Decimal("99.00"),
            recorded_at=recorded_at,
        )
        repo.bulk_create(db, [duplicate])
        db.commit()

        results = db.query(HealthScore).filter(HealthScore.data_source_id == data_source.id).all()
        assert len(results) == 1
        assert results[0].value == Decimal("80.00")
