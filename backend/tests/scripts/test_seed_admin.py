"""Tests for scripts/init/seed_admin.py: no publicly known admin password in production."""

import importlib.util
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models import Developer
from app.utils.config_utils import EnvironmentType
from tests.factories import DeveloperFactory

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "init" / "seed_admin.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seed_admin", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed_module = _load_module()


def _seed(db: Session, password: str, environment: EnvironmentType) -> None:
    with patch.object(seed_module, "SessionLocal", lambda: nullcontext(db)):
        seed_module.seed_admin("admin@example.org", password, environment=environment)


class TestSeedAdmin:
    def test_refuses_the_default_password_in_production(self, db: Session) -> None:
        # Act / Assert
        with pytest.raises(seed_module.DefaultAdminPasswordError):
            _seed(db, seed_module.DEFAULT_ADMIN_PASSWORD, EnvironmentType.PRODUCTION)

        assert db.query(Developer).count() == 0

    def test_seeds_production_with_a_real_password(self, db: Session) -> None:
        # Act
        _seed(db, "a-real-secret-8f2c", EnvironmentType.PRODUCTION)

        # Assert
        assert db.query(Developer).count() == 1

    def test_default_password_is_fine_outside_production(self, db: Session) -> None:
        """Local docker-compose relies on the placeholder."""
        # Act
        _seed(db, seed_module.DEFAULT_ADMIN_PASSWORD, EnvironmentType.LOCAL)

        # Assert
        assert db.query(Developer).count() == 1

    def test_existing_developer_skips_before_the_check(self, db: Session) -> None:
        """A live production database with a developer must not start failing its init job."""
        # Arrange
        DeveloperFactory()

        # Act: must not raise
        _seed(db, seed_module.DEFAULT_ADMIN_PASSWORD, EnvironmentType.PRODUCTION)

        # Assert
        assert db.query(Developer).count() == 1
