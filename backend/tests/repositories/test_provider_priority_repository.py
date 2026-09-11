"""Tests for ProviderPriorityRepository."""

import pytest
from sqlalchemy.orm import Session

from app.models import ProviderPriority
from app.repositories.provider_priority_repository import ProviderPriorityRepository
from app.schemas.enums import ProviderName


class TestProviderPriorityRepository:
    """Test ProviderPriorityRepository methods."""

    @pytest.fixture
    def repo(self) -> ProviderPriorityRepository:
        """Create ProviderPriorityRepository instance."""
        return ProviderPriorityRepository(ProviderPriority)

    def test_ensure_provider_exists_creates_new(self, db: Session, repo: ProviderPriorityRepository) -> None:
        """Should create a new provider priority if it doesn't exist."""
        # Arrange
        provider = ProviderName.APPLE

        # Act
        priority = repo.ensure_provider_exists(db, provider)

        # Assert
        assert priority is not None
        assert priority.provider == provider
        assert priority.priority == 1  # Default priority

        # Verify in database
        db_priority = db.query(ProviderPriority).filter_by(provider=provider).first()
        assert db_priority is not None
        assert db_priority.id == priority.id

    def test_ensure_provider_exists_returns_existing(self, db: Session, repo: ProviderPriorityRepository) -> None:
        """Should return existing provider priority without creating duplicate."""
        # Arrange
        provider = ProviderName.GARMIN
        first_priority = repo.ensure_provider_exists(db, provider)
        original_id = first_priority.id

        # Act
        second_priority = repo.ensure_provider_exists(db, provider)

        # Assert
        assert second_priority.id == original_id
        assert second_priority.provider == provider

        # Verify only one record exists
        count = db.query(ProviderPriority).filter_by(provider=provider).count()
        assert count == 1

    def test_ensure_provider_exists_multiple_providers(self, db: Session, repo: ProviderPriorityRepository) -> None:
        """Should handle multiple providers independently."""
        # Arrange & Act
        apple_priority = repo.ensure_provider_exists(db, ProviderName.APPLE)
        garmin_priority = repo.ensure_provider_exists(db, ProviderName.GARMIN)
        polar_priority = repo.ensure_provider_exists(db, ProviderName.POLAR)

        # Assert
        assert apple_priority.provider == ProviderName.APPLE
        assert garmin_priority.provider == ProviderName.GARMIN
        assert polar_priority.provider == ProviderName.POLAR

        # All should have different IDs
        assert len({apple_priority.id, garmin_priority.id, polar_priority.id}) == 3

    def test_get_all_returns_all_priorities(self, db: Session, repo: ProviderPriorityRepository) -> None:
        """Should return all provider priorities ordered by priority."""
        # Arrange - create some priorities
        repo.ensure_provider_exists(db, ProviderName.APPLE)
        repo.ensure_provider_exists(db, ProviderName.GARMIN)
        repo.ensure_provider_exists(db, ProviderName.POLAR)

        # Act
        all_priorities = repo.get_all_ordered(db)

        # Assert
        assert len(all_priorities) >= 3
        providers = [p.provider for p in all_priorities]
        assert ProviderName.APPLE in providers
        assert ProviderName.GARMIN in providers
        assert ProviderName.POLAR in providers

        # Verify ordering by priority (ascending)
        priorities_values = [p.priority for p in all_priorities]
        assert priorities_values == sorted(priorities_values)

    def test_get_all_empty_database(self, db: Session, repo: ProviderPriorityRepository) -> None:
        """Should return empty list when no priorities exist."""
        # Act
        all_priorities = repo.get_all_ordered(db)

        # Assert
        assert all_priorities == []

    def test_update_priority(self, db: Session, repo: ProviderPriorityRepository) -> None:
        """Should update provider priority value."""
        # Arrange
        provider = ProviderName.WHOOP
        priority_record = repo.ensure_provider_exists(db, provider)
        original_priority = priority_record.priority

        # Act - update priority
        new_priority_value = 10
        priority_record.priority = new_priority_value
        db.commit()
        db.refresh(priority_record)

        # Assert
        assert priority_record.priority == new_priority_value
        assert priority_record.priority != original_priority

        # Verify via repo
        updated = repo.ensure_provider_exists(db, provider)
        assert updated.priority == new_priority_value


class TestSeedMissingProviders:
    """Test ProviderPriorityRepository.seed_missing_providers."""

    @pytest.fixture
    def repo(self) -> ProviderPriorityRepository:
        return ProviderPriorityRepository(ProviderPriority)

    def test_empty_table_gets_given_order(self, db: Session, repo: ProviderPriorityRepository) -> None:
        """On a fresh table every provider is created, numbered 1..N in the order given."""
        providers = [ProviderName.GARMIN, ProviderName.APPLE, ProviderName.OURA]

        created = repo.seed_missing_providers(db, providers)
        db.commit()

        assert [p.provider for p in created] == providers
        assert [p.priority for p in created] == [1, 2, 3]
        assert [p.provider for p in repo.get_all_ordered(db)] == providers

    def test_missing_providers_are_appended_after_existing(self, db: Session, repo: ProviderPriorityRepository) -> None:
        """A deployment's configured order stays on top; new providers land below it."""
        repo.bulk_update(db, [(ProviderName.OURA, 1), (ProviderName.APPLE, 2)])
        db.commit()

        created = repo.seed_missing_providers(
            db, [ProviderName.APPLE, ProviderName.GARMIN, ProviderName.OURA, ProviderName.POLAR]
        )
        db.commit()

        assert [(p.provider, p.priority) for p in created] == [(ProviderName.GARMIN, 3), (ProviderName.POLAR, 4)]
        ordered = [(p.provider, p.priority) for p in repo.get_all_ordered(db)]
        assert ordered == [
            (ProviderName.OURA, 1),
            (ProviderName.APPLE, 2),
            (ProviderName.GARMIN, 3),
            (ProviderName.POLAR, 4),
        ]

    def test_existing_rows_are_untouched(self, db: Session, repo: ProviderPriorityRepository) -> None:
        """Seeding never changes the priority or timestamps of rows that already exist."""
        existing = repo.upsert(db, ProviderName.WHOOP, 7)
        db.commit()
        before = (existing.id, existing.priority, existing.updated_at)

        repo.seed_missing_providers(db, [ProviderName.WHOOP, ProviderName.SUUNTO])
        db.commit()

        after = repo.get_by_provider(db, ProviderName.WHOOP)
        assert after is not None
        assert (after.id, after.priority, after.updated_at) == before

    def test_is_idempotent(self, db: Session, repo: ProviderPriorityRepository) -> None:
        """A second run creates nothing and leaves the table as it was."""
        providers = [ProviderName.APPLE, ProviderName.GARMIN]
        repo.seed_missing_providers(db, providers)
        db.commit()
        snapshot = [(p.provider, p.priority) for p in repo.get_all_ordered(db)]

        created = repo.seed_missing_providers(db, providers)
        db.commit()

        assert created == []
        assert [(p.provider, p.priority) for p in repo.get_all_ordered(db)] == snapshot

    def test_default_order_covers_every_connectable_provider(self) -> None:
        """Every provider except UNKNOWN/INTERNAL has a default priority, with no duplicate numbers."""
        from app.schemas.enums import DEFAULT_PROVIDER_PRIORITY

        expected = {p for p in ProviderName if p not in (ProviderName.UNKNOWN, ProviderName.INTERNAL)}
        assert set(DEFAULT_PROVIDER_PRIORITY) == expected
        assert len(set(DEFAULT_PROVIDER_PRIORITY.values())) == len(DEFAULT_PROVIDER_PRIORITY)
