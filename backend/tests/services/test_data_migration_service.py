"""Tests for running one-off data migrations at most once per instance."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import DataMigration
from app.services.data_migration_service import data_migration_service

NAME = "test_migration"


class TestDataMigrationService:
    def test_clean_run_is_recorded_and_not_repeated(self, db: Session) -> None:
        migrate = MagicMock(return_value=True)

        data_migration_service.run(db, NAME, migrate)
        data_migration_service.run(db, NAME, migrate)

        migrate.assert_called_once()
        assert db.get(DataMigration, NAME) is not None

    def test_incomplete_run_is_retried(self, db: Session) -> None:
        migrate = MagicMock(return_value=False)

        data_migration_service.run(db, NAME, migrate)
        data_migration_service.run(db, NAME, migrate)

        assert migrate.call_count == 2
        assert db.get(DataMigration, NAME) is None

    def test_failed_run_is_not_recorded_and_releases_the_lock(self, db: Session) -> None:
        with pytest.raises(RuntimeError):
            data_migration_service.run(db, NAME, MagicMock(side_effect=RuntimeError("boom")))

        assert db.get(DataMigration, NAME) is None
        assert data_migration_service.repo.try_lock(db, NAME)
        data_migration_service.repo.unlock(db, NAME)

    def test_dry_run_is_never_recorded(self, db: Session) -> None:
        migrate = MagicMock(return_value=True)

        data_migration_service.run(db, NAME, migrate, dry_run=True)

        migrate.assert_called_once()
        assert db.get(DataMigration, NAME) is None

    def test_run_held_by_another_instance_is_skipped(self, db: Session, engine: Any) -> None:
        migrate = MagicMock(return_value=True)
        key = {"key": f"data_migration:{NAME}"}
        with engine.connect() as other:
            other.execute(text("SELECT pg_advisory_lock(hashtextextended(:key, 0))"), key)
            try:
                data_migration_service.run(db, NAME, migrate)
            finally:
                other.execute(text("SELECT pg_advisory_unlock(hashtextextended(:key, 0))"), key)

        migrate.assert_not_called()
        assert db.get(DataMigration, NAME) is None
