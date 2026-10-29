"""
Tests for HealthScoreRepository.

Tests cover:
- Basic CRUD via CrudRepository base
- get_with_filters: category, provider, date range, user scoping
- get_latest_by_category
- get_latest_per_category
- bulk_create with on_conflict_do_nothing
- bulk_create_keeping_highest
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

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


def _body_battery(user_id: UUID, recorded_at: datetime, value: str | None) -> HealthScoreCreate:
    return HealthScoreCreate(
        id=uuid4(),
        user_id=user_id,
        provider=ProviderName.GARMIN,
        category=HealthScoreCategory.BODY_BATTERY,
        value=Decimal(value) if value is not None else None,
        recorded_at=recorded_at,
    )


class TestHealthScoreRepositoryBulkCreateKeepingHighest:
    def test_a_higher_value_replaces_the_stored_one(self, db: Session, repo: HealthScoreRepository) -> None:
        user = UserFactory()
        day = datetime(2026, 10, 28, tzinfo=timezone.utc)

        first = repo.bulk_create_keeping_highest(db, [_body_battery(user.id, day, "46")])
        higher = repo.bulk_create_keeping_highest(db, [_body_battery(user.id, day, "78")])
        lower = repo.bulk_create_keeping_highest(db, [_body_battery(user.id, day, "60")])
        db.commit()

        [score] = db.query(HealthScore).filter(HealthScore.user_id == user.id).all()
        assert score.value == Decimal("78")
        assert (first.inserted, first.updated) == (1, 0)
        assert (higher.inserted, higher.updated) == (0, 1)
        assert (lower.inserted, lower.updated) == (0, 0)

    def test_one_batch_keeps_the_highest_of_a_day(self, db: Session, repo: HealthScoreRepository) -> None:
        # ON CONFLICT DO UPDATE can't touch a row twice in one statement
        user = UserFactory()
        day = datetime(2026, 10, 28, tzinfo=timezone.utc)
        scores = [_body_battery(user.id, day, value) for value in ("46", "78", "60")]

        written = repo.bulk_create_keeping_highest(db, scores)
        db.commit()

        [score] = db.query(HealthScore).filter(HealthScore.user_id == user.id).all()
        assert score.value == Decimal("78")
        assert (written.inserted, written.updated) == (1, 0)

    def test_a_value_replaces_a_stored_empty_one(self, db: Session, repo: HealthScoreRepository) -> None:
        user = UserFactory()
        day = datetime(2026, 10, 28, tzinfo=timezone.utc)
        repo.bulk_create(db, [_body_battery(user.id, day, None)])

        written = repo.bulk_create_keeping_highest(db, [_body_battery(user.id, day, "78")])
        db.commit()

        [score] = db.query(HealthScore).filter(HealthScore.user_id == user.id).all()
        assert score.value == Decimal("78")
        assert (written.inserted, written.updated) == (0, 1)

    def test_a_score_without_a_value_is_skipped(self, db: Session, repo: HealthScoreRepository) -> None:
        user = UserFactory()

        written = repo.bulk_create_keeping_highest(db, [_body_battery(user.id, datetime.now(timezone.utc), None)])

        assert (written.inserted, written.updated) == (0, 0)
        assert db.query(HealthScore).filter(HealthScore.user_id == user.id).count() == 0

    def test_empty(self, db: Session, repo: HealthScoreRepository) -> None:
        written = repo.bulk_create_keeping_highest(db, [])

        assert (written.inserted, written.updated) == (0, 0)
