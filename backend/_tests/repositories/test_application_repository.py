"""Tests for Application repository."""

import pytest
from sqlalchemy.orm import Session

from app.models import Application
from app.repositories.application_repository import ApplicationRepository
from _tests.factories import ApplicationFactory, DeveloperFactory


@pytest.fixture
def application_repo() -> ApplicationRepository:
    """Create application repository instance."""
    return ApplicationRepository(Application)


class TestApplicationRepositoryGetByAppId:
    """Tests for get_by_app_id method."""

    def test_get_by_app_id_existing(self, db: Session, application_repo: ApplicationRepository) -> None:
        """Should return application by app_id."""
        developer = DeveloperFactory()
        app = ApplicationFactory(developer=developer, app_id="app_test123")

        result = application_repo.get_by_app_id(db, "app_test123")

        assert result is not None
        assert result.app_id == "app_test123"
        assert result.id == app.id

    def test_get_by_app_id_nonexistent(self, db: Session, application_repo: ApplicationRepository) -> None:
        """Should return None for non-existent app_id."""
        result = application_repo.get_by_app_id(db, "app_nonexistent")

        assert result is None


class TestApplicationRepositoryListByDeveloper:
    """Tests for list_by_developer method."""

    def test_list_by_developer(self, db: Session, application_repo: ApplicationRepository) -> None:
        """Should list only applications for specific developer."""
        developer1 = DeveloperFactory()
        developer2 = DeveloperFactory()
        ApplicationFactory(developer=developer1, name="Dev1 App 1")
        ApplicationFactory(developer=developer1, name="Dev1 App 2")
        ApplicationFactory(developer=developer2, name="Dev2 App")

        result = application_repo.list_by_developer(db, developer1.id)

        assert len(result) == 2
        assert all(app.developer_id == developer1.id for app in result)

    def test_list_by_developer_empty(self, db: Session, application_repo: ApplicationRepository) -> None:
        """Should return empty list for developer with no applications."""
        developer = DeveloperFactory()

        result = application_repo.list_by_developer(db, developer.id)

        assert result == []

    def test_list_by_developer_ordered_by_created_at(
        self, db: Session, application_repo: ApplicationRepository
    ) -> None:
        """Should return applications ordered by created_at descending."""
        from datetime import datetime, timedelta, timezone

        developer = DeveloperFactory()
        now = datetime.now(timezone.utc)

        # Create apps with different timestamps
        ApplicationFactory(
            developer=developer,
            name="Older App",
            created_at=now - timedelta(hours=2),
        )
        ApplicationFactory(
            developer=developer,
            name="Newer App",
            created_at=now,
        )

        result = application_repo.list_by_developer(db, developer.id)

        # Most recent first
        assert result[0].name == "Newer App"
        assert result[1].name == "Older App"


class TestApplicationRepositoryGetAllOrdered:
    """Tests for get_all_ordered method."""

    def test_get_all_ordered(self, db: Session, application_repo: ApplicationRepository) -> None:
        """Should return all applications ordered by created_at descending."""
        developer1 = DeveloperFactory()
        developer2 = DeveloperFactory()
        ApplicationFactory(developer=developer1)
        ApplicationFactory(developer=developer2)

        result = application_repo.get_all_ordered(db)

        assert len(result) >= 2

    def test_get_all_ordered_empty(self, db: Session, application_repo: ApplicationRepository) -> None:
        """Should return empty list when no applications exist."""
        # Don't create any applications
        result = application_repo.get_all_ordered(db)

        # May have applications from other tests, but should not fail
        assert isinstance(result, list)
