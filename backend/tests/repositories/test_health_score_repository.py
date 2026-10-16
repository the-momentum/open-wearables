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
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import HealthScore, ProviderPriority
from app.repositories import ProviderPriorityRepository
from app.repositories.health_score_repository import HealthScoreRepository
from app.schemas.enums import DeviceType, HealthScoreCategory, ProviderName
from app.schemas.model_crud.activities import HealthScoreCreate, HealthScoreQueryParams
from tests.factories import (
    DataSourceFactory,
    EventRecordFactory,
    HealthScoreFactory,
    SleepDetailsFactory,
    UserFactory,
)


@pytest.fixture
def repo() -> HealthScoreRepository:
    return HealthScoreRepository(HealthScore)


NIGHT = datetime(2026, 9, 24, 7, tzinfo=timezone.utc)


def _orders(db: Session) -> tuple[dict[ProviderName, int], dict[DeviceType, int]]:
    return ProviderPriorityRepository(ProviderPriority).get_priority_order(db), {}


def _prioritise(db: Session, *providers: ProviderName) -> None:
    priorities = ProviderPriorityRepository(ProviderPriority)
    for rank, provider in enumerate(providers, start=1):
        priorities.upsert(db, provider, rank)


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

    def test_create_duplicate_without_a_source_returns_existing(self, db: Session, repo: HealthScoreRepository) -> None:
        user = UserFactory()
        recorded_at = datetime(2026, 9, 24, 7, tzinfo=timezone.utc)
        scores = [
            HealthScoreCreate(
                id=uuid4(),
                user_id=user.id,
                provider=ProviderName.WHOOP,
                category=HealthScoreCategory.RECOVERY,
                value=Decimal(value),
                recorded_at=recorded_at,
            )
            for value in ("70.00", "75.00")
        ]

        first = repo.create(db, scores[0])
        result = repo.create(db, scores[1])

        assert result.id == first.id
        assert result.value == Decimal("70.00")


class TestHealthScoreRepositoryGetWithFilters:
    def test_filter_by_category(self, db: Session, repo: HealthScoreRepository) -> None:
        user = UserFactory()
        data_source = DataSourceFactory(user=user)
        HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.SLEEP)
        HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.SLEEP)
        HealthScoreFactory(data_source=data_source, category=HealthScoreCategory.RECOVERY)

        results, total = repo.get_with_filters(
            db, user.id, HealthScoreQueryParams(category=HealthScoreCategory.SLEEP), {}, {}
        )

        assert total == 2
        assert all(s.category == HealthScoreCategory.SLEEP for s, _ in results)

    def test_filter_by_provider(self, db: Session, repo: HealthScoreRepository) -> None:
        user = UserFactory()
        data_source = DataSourceFactory(user=user)
        HealthScoreFactory(data_source=data_source, provider=ProviderName.GARMIN)
        HealthScoreFactory(data_source=data_source, provider=ProviderName.OURA)

        results, total = repo.get_with_filters(
            db, user.id, HealthScoreQueryParams(provider=ProviderName.GARMIN), {}, {}
        )

        assert total == 1
        assert results[0][0].provider == ProviderName.GARMIN

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
            {},
            {},
        )

        assert total == 2

    def test_scoped_to_user(self, db: Session, repo: HealthScoreRepository) -> None:
        user_a = UserFactory()
        user_b = UserFactory()
        HealthScoreFactory(data_source=DataSourceFactory(user=user_a))
        HealthScoreFactory(data_source=DataSourceFactory(user=user_b))

        results, total = repo.get_with_filters(db, user_a.id, HealthScoreQueryParams(), {}, {})

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

    def test_bulk_create_keeps_scores_of_two_sources_at_the_same_time(
        self, db: Session, repo: HealthScoreRepository
    ) -> None:
        user = UserFactory()
        garmin = DataSourceFactory(user=user, provider=ProviderName.GARMIN)
        oura = DataSourceFactory(user=user, provider=ProviderName.OURA)
        recorded_at = datetime(2026, 9, 24, 7, tzinfo=timezone.utc)

        repo.bulk_create(
            db,
            [
                HealthScoreCreate(
                    id=uuid4(),
                    user_id=user.id,
                    data_source_id=source.id,
                    provider=ProviderName.INTERNAL,
                    category=HealthScoreCategory.SLEEP,
                    value=Decimal("80.00"),
                    recorded_at=recorded_at,
                )
                for source in (garmin, oura)
            ],
        )
        db.commit()

        assert db.query(HealthScore).filter(HealthScore.user_id == user.id).count() == 2

    def test_bulk_create_ignores_duplicate_scores_without_a_source(
        self, db: Session, repo: HealthScoreRepository
    ) -> None:
        user = UserFactory()
        recorded_at = datetime(2026, 9, 24, 7, tzinfo=timezone.utc)
        for value in ("80.00", "99.00"):
            repo.bulk_create(
                db,
                [
                    HealthScoreCreate(
                        id=uuid4(),
                        user_id=user.id,
                        provider=ProviderName.OURA,
                        category=HealthScoreCategory.SLEEP,
                        value=Decimal(value),
                        recorded_at=recorded_at,
                    )
                ],
            )
            db.commit()

        scores = db.query(HealthScore).filter(HealthScore.user_id == user.id).all()
        assert [score.value for score in scores] == [Decimal("80.00")]


class TestHealthScoreRepositorySourcePriority:
    def _ow(self, data_source: Any, recorded_at: datetime = NIGHT, **kwargs: Any) -> HealthScore:
        return HealthScoreFactory(
            data_source=data_source, provider=ProviderName.INTERNAL, recorded_at=recorded_at, **kwargs
        )

    def test_keeps_the_ow_score_of_the_highest_priority_source(self, db: Session, repo: HealthScoreRepository) -> None:
        _prioritise(db, ProviderName.GARMIN, ProviderName.OURA)
        user = UserFactory()
        garmin = self._ow(DataSourceFactory(user=user, provider=ProviderName.GARMIN))
        self._ow(DataSourceFactory(user=user, provider=ProviderName.OURA), NIGHT + timedelta(hours=1))

        results, total = repo.get_with_filters(db, user.id, HealthScoreQueryParams(), *_orders(db))

        assert total == 1
        assert [score.id for score, _ in results] == [garmin.id]

    def test_priority_decides_not_the_order_of_writes(self, db: Session, repo: HealthScoreRepository) -> None:
        _prioritise(db, ProviderName.OURA, ProviderName.GARMIN)
        user = UserFactory()
        self._ow(DataSourceFactory(user=user, provider=ProviderName.GARMIN))
        oura = self._ow(DataSourceFactory(user=user, provider=ProviderName.OURA))

        results, _ = repo.get_with_filters(db, user.id, HealthScoreQueryParams(), *_orders(db))

        assert [score.id for score, _ in results] == [oura.id]

    def test_one_ow_score_per_category(self, db: Session, repo: HealthScoreRepository) -> None:
        user = UserFactory()
        source = DataSourceFactory(user=user, provider=ProviderName.GARMIN)
        self._ow(source, category=HealthScoreCategory.SLEEP)
        self._ow(source, category=HealthScoreCategory.RESILIENCE)

        _, total = repo.get_with_filters(db, user.id, HealthScoreQueryParams(), *_orders(db))

        assert total == 2

    def test_the_night_wins_over_an_unflagged_nap_of_the_same_source(
        self, db: Session, repo: HealthScoreRepository
    ) -> None:
        """SDK naps can come without the nap flag (#938) and get a sleep score of their own."""
        user = UserFactory()
        source = DataSourceFactory(user=user, provider=ProviderName.APPLE)
        scores = []
        for wake_up, hours in ((NIGHT, 8), (NIGHT + timedelta(hours=8), 1)):
            session = EventRecordFactory(
                data_source=source,
                category="sleep",
                type="sleep",
                start_datetime=wake_up - timedelta(hours=hours),
                end_datetime=wake_up,
                duration_seconds=hours * 3600,
            )
            SleepDetailsFactory(event_record=session, is_nap=False, sleep_total_duration_minutes=hours * 60 - 20)
            scores.append(self._ow(source, wake_up, event_record_id=session.id))

        results, _ = repo.get_with_filters(db, user.id, HealthScoreQueryParams(), *_orders(db))

        assert [score.id for score, _ in results] == [scores[0].id]

    def test_days_are_utc_dates_whatever_the_database_time_zone(self, db: Session, repo: HealthScoreRepository) -> None:
        """01:00 UTC is still the previous evening in New York; it must not split the day."""
        db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
        _prioritise(db, ProviderName.GARMIN, ProviderName.OURA)
        user = UserFactory()
        garmin = self._ow(DataSourceFactory(user=user, provider=ProviderName.GARMIN), NIGHT - timedelta(hours=6))
        self._ow(DataSourceFactory(user=user, provider=ProviderName.OURA), NIGHT)

        results, _ = repo.get_with_filters(db, user.id, HealthScoreQueryParams(), *_orders(db))

        assert [score.id for score, _ in results] == [garmin.id]

    def test_provider_scores_are_returned_as_they_are(self, db: Session, repo: HealthScoreRepository) -> None:
        user = UserFactory()
        garmin = DataSourceFactory(user=user, provider=ProviderName.GARMIN)
        oura = DataSourceFactory(user=user, provider=ProviderName.OURA)
        HealthScoreFactory(data_source=garmin, provider=ProviderName.GARMIN, recorded_at=NIGHT)
        HealthScoreFactory(data_source=oura, provider=ProviderName.OURA, recorded_at=NIGHT)
        self._ow(garmin)
        self._ow(oura)

        results, total = repo.get_with_filters(db, user.id, HealthScoreQueryParams(), *_orders(db))

        assert total == 3
        assert sorted(score.provider for score, _ in results) == ["garmin", "internal", "oura"]

    def test_an_ow_score_with_a_source_beats_one_without(self, db: Session, repo: HealthScoreRepository) -> None:
        """Even when the source's provider is missing from the priorities."""
        user = UserFactory()
        sourced = self._ow(
            DataSourceFactory(user=user, provider=ProviderName.GARMIN), category=HealthScoreCategory.RESILIENCE
        )
        HealthScoreFactory(
            data_source_id=None,
            user_id=user.id,
            provider=ProviderName.INTERNAL,
            category=HealthScoreCategory.RESILIENCE,
            recorded_at=NIGHT,
        )

        results, _ = repo.get_with_filters(db, user.id, HealthScoreQueryParams(), {}, {})

        assert [score.id for score, _ in results] == [sourced.id]

    def test_paging_counts_the_picked_scores(self, db: Session, repo: HealthScoreRepository) -> None:
        user = UserFactory()
        garmin = DataSourceFactory(user=user, provider=ProviderName.GARMIN)
        oura = DataSourceFactory(user=user, provider=ProviderName.OURA)
        for day in range(3):
            self._ow(garmin, NIGHT + timedelta(days=day))
            self._ow(oura, NIGHT + timedelta(days=day))

        results, total = repo.get_with_filters(db, user.id, HealthScoreQueryParams(offset=1, limit=1), *_orders(db))

        assert total == 3
        assert [score.recorded_at.date() for score, _ in results] == [(NIGHT + timedelta(days=1)).date()]

    def test_ow_score_without_a_source_is_kept(self, db: Session, repo: HealthScoreRepository) -> None:
        user = UserFactory()
        resilience = HealthScoreFactory(
            data_source_id=None,
            user_id=user.id,
            provider=ProviderName.INTERNAL,
            category=HealthScoreCategory.RESILIENCE,
            recorded_at=NIGHT,
        )

        results, _ = repo.get_with_filters(db, user.id, HealthScoreQueryParams(), *_orders(db))

        assert results == [(resilience, None)]

    def test_returns_each_score_with_its_source(self, db: Session, repo: HealthScoreRepository) -> None:
        user = UserFactory()
        source = DataSourceFactory(user=user, provider=ProviderName.GARMIN)
        score = self._ow(source)

        results, _ = repo.get_with_filters(db, user.id, HealthScoreQueryParams(), *_orders(db))

        assert results == [(score, source)]
