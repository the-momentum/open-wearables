"""Tests for the legacy ``google`` provider split, focused on the retry after a failed run.

``scripts/start/app.sh`` runs the split before ``init_provider_settings.py`` and
``init_provider_priorities.py``, but a failed split does not stop startup, so both seeds
create their ``google_health`` rows. The retry on the next start then finds the target
rows already there. ``provider_settings.provider`` is the primary key and
``provider_priority.provider`` is unique, so a plain rename raises and the whole split
rolls back, connections included. See scripts/data_migrations/split_google_provider.py.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.factories import UserConnectionFactory

LEGACY = "google"
API = "google_health"

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "split_google_provider.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("split_google_provider", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


split_google_provider = _load_module().split_google_provider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _add_settings(db: Session, provider: str, *, is_enabled: bool, live_sync_mode: str | None) -> None:
    db.execute(
        text("INSERT INTO provider_settings (provider, is_enabled, live_sync_mode) VALUES (:p, :e, :m)"),
        {"p": provider, "e": is_enabled, "m": live_sync_mode},
    )


def _add_priority(db: Session, provider: str, priority: int) -> None:
    db.execute(
        text(
            "INSERT INTO provider_priority (id, provider, priority, created_at, updated_at)"
            " VALUES (gen_random_uuid(), :p, :n, now(), now())"
        ),
        {"p": provider, "n": priority},
    )


def _legacy_oauth_connection(db: Session) -> str:
    connection = UserConnectionFactory(provider="garmin")
    db.execute(text("UPDATE user_connection SET provider = :p WHERE id = :id"), {"p": LEGACY, "id": connection.id})
    return str(connection.id)


def _settings(db: Session) -> dict[str, tuple[bool, str | None]]:
    rows = db.execute(
        text("SELECT provider, is_enabled, live_sync_mode FROM provider_settings WHERE provider IN (:l, :a)"),
        {"l": LEGACY, "a": API},
    )
    return {row[0]: (row[1], row[2]) for row in rows}


def _priorities(db: Session) -> dict[str, int]:
    rows = db.execute(
        text("SELECT provider, priority FROM provider_priority WHERE provider IN (:l, :a)"),
        {"l": LEGACY, "a": API},
    )
    return {row[0]: row[1] for row in rows}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSplitGoogleProvider:
    def test_renames_when_no_target_row_exists(self, db: Session) -> None:
        # Arrange
        _add_settings(db, LEGACY, is_enabled=False, live_sync_mode="pull")
        _add_priority(db, LEGACY, 3)

        # Act
        result = split_google_provider(db, dry_run=False)

        # Assert
        assert result["provider_settings"] == 1
        assert result["provider_priority"] == 1
        assert _settings(db) == {API: (False, "pull")}
        assert _priorities(db) == {API: 3}

    def test_retry_after_seed_folds_instead_of_colliding(self, db: Session) -> None:
        """A failed first run is followed by the seeds; the retry must still move everything."""
        # Arrange
        _add_settings(db, LEGACY, is_enabled=False, live_sync_mode="pull")
        _add_settings(db, API, is_enabled=True, live_sync_mode=None)
        _add_priority(db, LEGACY, 3)
        _add_priority(db, API, 12)
        connection_id = _legacy_oauth_connection(db)

        # Act
        result = split_google_provider(db, dry_run=False)

        # Assert
        assert result["user_connection_api"] == 1
        provider = db.execute(
            text("SELECT provider FROM user_connection WHERE id = :id"), {"id": connection_id}
        ).scalar_one()
        assert provider == API
        # The legacy row is what the deployment ran with; the seeded one only held defaults.
        assert _settings(db) == {API: (False, "pull")}
        assert _priorities(db) == {API: 3}

    def test_retry_is_idempotent(self, db: Session) -> None:
        # Arrange
        _add_settings(db, LEGACY, is_enabled=False, live_sync_mode="pull")
        _add_settings(db, API, is_enabled=True, live_sync_mode=None)
        _add_priority(db, LEGACY, 3)
        _add_priority(db, API, 12)
        split_google_provider(db, dry_run=False)

        # Act
        second = split_google_provider(db, dry_run=False)

        # Assert
        assert not any(second.values())
        assert _settings(db) == {API: (False, "pull")}
