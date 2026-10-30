"""Tests for scripts/init/seed_admin.py: no publicly known admin password in production."""

import importlib.util
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models import Developer, RefreshToken
from app.services import refresh_token_service
from app.utils import security
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

ADMIN_EMAIL = "admin@example.org"


def _seed(db: Session, password: str, environment: EnvironmentType) -> None:
    # The script imports verify_password directly, so it misses the fast-hashing fixture's patch.
    with (
        patch.object(seed_module, "SessionLocal", lambda: nullcontext(db)),
        patch.object(seed_module, "verify_password", security.verify_password),
    ):
        seed_module.seed_admin(ADMIN_EMAIL, password, environment=environment)


def _open_sessions(db: Session) -> int:
    return db.query(RefreshToken).filter(RefreshToken.revoked_at.is_(None)).count()


def _admin_password_is(db: Session, password: str) -> bool:
    admin = db.query(Developer).filter(Developer.email == ADMIN_EMAIL).one()
    db.refresh(admin)
    return security.verify_password(password, admin.hashed_password)


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


class TestRotateDefaultPassword:
    """An admin still on the public default moves to ADMIN_PASSWORD once that is set."""

    @pytest.mark.parametrize("environment", [EnvironmentType.PRODUCTION, EnvironmentType.LOCAL])
    def test_replaces_the_default_with_admin_password(self, db: Session, environment: EnvironmentType) -> None:
        # Arrange
        admin = DeveloperFactory(email=ADMIN_EMAIL, password=seed_module.DEFAULT_ADMIN_PASSWORD)
        refresh_token_service.create_developer_refresh_token(db, admin.id)

        # Act
        _seed(db, "a-real-secret-8f2c", environment)

        # Assert
        assert _admin_password_is(db, "a-real-secret-8f2c")
        assert _open_sessions(db) == 0

    def test_leaves_the_default_when_admin_password_is_unset(self, db: Session) -> None:
        """Startup must not fail: the login refuses the default instead, and older sessions end."""
        # Arrange
        admin = DeveloperFactory(email=ADMIN_EMAIL, password=seed_module.DEFAULT_ADMIN_PASSWORD)
        refresh_token_service.create_developer_refresh_token(db, admin.id)

        # Act: must not raise
        _seed(db, seed_module.DEFAULT_ADMIN_PASSWORD, EnvironmentType.PRODUCTION)

        # Assert
        assert _admin_password_is(db, seed_module.DEFAULT_ADMIN_PASSWORD)
        assert _open_sessions(db) == 0

    def test_keeps_a_password_the_admin_already_changed(self, db: Session) -> None:
        """ADMIN_PASSWORD must not undo a change made in the portal."""
        # Arrange
        DeveloperFactory(email=ADMIN_EMAIL, password="changed-in-the-portal")

        # Act
        _seed(db, "a-real-secret-8f2c", EnvironmentType.PRODUCTION)

        # Assert
        assert _admin_password_is(db, "changed-in-the-portal")
